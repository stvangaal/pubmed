<?php
/**
 * Plugin Name: PubMed Pipeline
 * Description: Registers the custom taxonomy and meta fields required by the PubMed digest pipeline.
 * Version: 1.0.0
 * Author: PubMed Digest
 *
 * Upload this file to wp-content/plugins/ and activate it in the WordPress admin.
 */

// owner: wp-publish

// --- Custom taxonomy: clinical_topics ---

add_action('init', function () {
    register_taxonomy('clinical_topics', 'post', [
        'label'        => 'Clinical Topics',
        'public'       => true,
        'hierarchical' => false,
        'show_in_rest' => true,
        'rest_base'    => 'clinical_topics',
    ]);
});

// --- Article meta fields (exposed via REST API) ---

add_action('init', function () {
    $meta_fields = [
        'pmid'         => 'string',
        'triage_score' => 'string',
        'journal'      => 'string',
        'pub_date'     => 'string',
        'source_topic' => 'string',
        'preindex'     => 'string',
    ];

    foreach ($meta_fields as $key => $type) {
        register_post_meta('post', $key, [
            'show_in_rest'  => true,
            'single'        => true,
            'type'          => $type,
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);
    }
});

// --- Custom REST endpoint for member preferences ---
// Requires WP_DIGEST_API_SECRET defined in wp-config.php.

add_action('rest_api_init', function () {
    register_rest_route('digest/v1', '/members', [
        'methods'             => 'GET',
        'callback'            => 'pubmed_pipeline_get_members',
        'permission_callback' => 'pubmed_pipeline_verify_secret',
    ]);
});

function pubmed_pipeline_verify_secret(WP_REST_Request $request): bool {
    $expected = defined('WP_DIGEST_API_SECRET') ? WP_DIGEST_API_SECRET : '';
    if (!$expected) {
        return false;
    }
    return $request->get_header('X-Digest-Secret') === $expected;
}

function pubmed_pipeline_get_members(): WP_REST_Response {
    $users = get_users(['role__in' => ['subscriber', 'um_member']]);
    $members = [];

    foreach ($users as $user) {
        $topics_raw = get_user_meta($user->ID, 'clinical_topics', true);
        $topics = is_array($topics_raw) ? $topics_raw : [];

        $members[] = [
            'email'        => $user->user_email,
            'display_name' => $user->display_name,
            'topics'       => array_values($topics),
        ];
    }

    return new WP_REST_Response($members, 200);
}
