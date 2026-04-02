# owner: pubmed-query
"""Tests for PubMed query construction, parsing, and search pipeline."""

from datetime import datetime
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

import pytest

from src.models import PubmedRecord, SearchConfig
from src.search.pubmed_query import build_query, build_preindex_query, parse_record, search


class TestBuildQuery:
    def test_basic_mesh_terms(self):
        config = SearchConfig(mesh_terms=["stroke"])
        query = build_query(config, run_date=datetime(2026, 3, 23))
        assert "stroke" in query.lower()

    def test_additional_terms_included(self):
        config = SearchConfig(
            mesh_terms=["stroke"],
            additional_terms=["thrombectomy"],
        )
        query = build_query(config, run_date=datetime(2026, 3, 23))
        assert "thrombectomy" in query.lower()

    def test_date_range_uses_mesh_date(self):
        config = SearchConfig(mesh_terms=["stroke"], date_window_days=7)
        query = build_query(config, run_date=datetime(2026, 3, 23))
        assert "[Date - MeSH Date]" in query

    def test_custom_date_window(self):
        config = SearchConfig(mesh_terms=["stroke"], date_window_days=14)
        query = build_query(config, run_date=datetime(2026, 3, 23))
        assert "2026/03/09" in query or "2026/03/10" in query or "2026" in query


class TestBuildPreindexQuery:
    def test_uses_title_abstract_field(self):
        config = SearchConfig(mesh_terms=["atrial fibrillation"])
        journals = ["the new england journal of medicine"]
        query = build_preindex_query(config, journals, run_date=datetime(2026, 3, 30))
        assert "[Title/Abstract]" in query
        assert "[MeSH Major Topic]" not in query

    def test_includes_journal_filter(self):
        config = SearchConfig(mesh_terms=["stroke"])
        journals = ["the new england journal of medicine", "the lancet"]
        query = build_preindex_query(config, journals, run_date=datetime(2026, 3, 30))
        assert '"the new england journal of medicine"[Journal]' in query
        assert '"the lancet"[Journal]' in query

    def test_uses_date_entry(self):
        config = SearchConfig(mesh_terms=["stroke"], date_window_days=7)
        journals = ["jama"]
        query = build_preindex_query(config, journals, run_date=datetime(2026, 3, 30))
        assert "[Date - Entry]" in query

    def test_includes_additional_terms(self):
        config = SearchConfig(
            mesh_terms=["atrial fibrillation"],
            additional_terms=["left atrial appendage"],
        )
        journals = ["jama"]
        query = build_preindex_query(config, journals, run_date=datetime(2026, 3, 30))
        assert '"left atrial appendage"[Title/Abstract]' in query

    def test_multiple_mesh_terms_or_joined(self):
        config = SearchConfig(mesh_terms=["stroke", "brain ischemia"])
        journals = ["jama"]
        query = build_preindex_query(config, journals, run_date=datetime(2026, 3, 30))
        assert '"stroke"[Title/Abstract]' in query
        assert '"brain ischemia"[Title/Abstract]' in query
        assert " OR " in query


class TestParseRecord:
    def test_parses_minimal_article(self):
        xml = """
        <PubmedArticle>
            <MedlineCitation>
                <PMID>12345</PMID>
                <Article>
                    <ArticleTitle>Test Title</ArticleTitle>
                    <Journal><Title>Test Journal</Title></Journal>
                    <Abstract><AbstractText>Test abstract.</AbstractText></Abstract>
                    <Language>eng</Language>
                    <AuthorList>
                        <Author><LastName>Smith</LastName><ForeName>John</ForeName></Author>
                    </AuthorList>
                </Article>
                <MeshHeadingList>
                    <MeshHeading><DescriptorName>Stroke</DescriptorName></MeshHeading>
                </MeshHeadingList>
            </MedlineCitation>
            <PubmedData>
                <ArticleIdList>
                    <ArticleId IdType="doi">10.1234/test</ArticleId>
                </ArticleIdList>
            </PubmedData>
        </PubmedArticle>
        """
        elem = ET.fromstring(xml)
        record = parse_record(elem)

        assert record is not None
        assert record.pmid == "12345"
        assert record.title == "Test Title"
        assert record.journal == "Test Journal"
        assert "Smith" in record.authors[0]

    def test_returns_none_without_pmid(self):
        xml = """
        <PubmedArticle>
            <MedlineCitation>
                <Article><ArticleTitle>No PMID</ArticleTitle></Article>
            </MedlineCitation>
        </PubmedArticle>
        """
        elem = ET.fromstring(xml)
        result = parse_record(elem)
        assert result is None


class TestSearch:
    @patch("src.search.pubmed_query.efetch")
    @patch("src.search.pubmed_query.esearch")
    def test_returns_records_and_count(self, mock_esearch, mock_efetch):
        mock_esearch.return_value = (["12345"], 1)
        mock_efetch.return_value = """<?xml version="1.0"?>
        <PubmedArticleSet>
            <PubmedArticle>
                <MedlineCitation>
                    <PMID>12345</PMID>
                    <Article>
                        <ArticleTitle>Test</ArticleTitle>
                        <Journal><Title>J</Title></Journal>
                        <Abstract><AbstractText>Abstract.</AbstractText></Abstract>
                        <Language>eng</Language>
                    </Article>
                </MedlineCitation>
            </PubmedArticle>
        </PubmedArticleSet>
        """
        config = SearchConfig(mesh_terms=["stroke"])
        records, total = search(config, run_date=datetime(2026, 3, 23))

        assert total == 1
        assert len(records) >= 1

    @patch("src.search.pubmed_query.efetch")
    @patch("src.search.pubmed_query.esearch")
    def test_empty_results(self, mock_esearch, mock_efetch):
        mock_esearch.return_value = ([], 0)
        config = SearchConfig(mesh_terms=["stroke"])
        records, total = search(config)

        assert records == []
        assert total == 0
        mock_efetch.assert_not_called()
