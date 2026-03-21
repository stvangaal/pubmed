# [Spec Name] — Implementation Plan

<!-- Plans are ephemeral documents. They are useful during implementation
     but are not governed artifacts. Once the spec reaches "implemented"
     status, this plan is historical context only. -->

**Spec:** `docs/specs/[spec-name].spec.md`

**Goal:** <!-- One sentence: what does implementing this spec achieve? -->

**Prerequisites:**
<!-- What must exist before implementation can begin?
     - Required specs that must be implemented or stubbed
     - Required definitions that must exist (at least at v0)
     - External dependencies (libraries, data, access) -->

**Architecture:** <!-- 2-3 sentences on the implementation approach -->

**Tech stack:** <!-- Key technologies and libraries -->

---

## File Structure

```
<!-- List all files that will be created or modified -->
```

---

## Task 1: [Component/Feature Name]

**Files:**
- Create: `exact/path/to/file.py`
- Create: `tests/exact/path/to/test_file.py`

### Step 1: Write failing tests

<!-- Complete test code — not pseudocode. Every assertion specific. -->

### Step 2: Verify tests fail

```bash
# Exact command to run
```

Expected: <!-- Exact error -->

### Step 3: Implement

<!-- Complete implementation code — not pseudocode. -->

### Step 4: Verify tests pass

```bash
# Exact command to run
```

Expected: PASS

### Step 5: Commit

```bash
git add [specific files]
git commit -m "[message]"
```

---

<!-- Repeat Task sections as needed -->

## Final Verification

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Register updated with owned files
- [ ] contracts.yaml updated (if definition pins changed)
- [ ] Spec status set to `implemented`
