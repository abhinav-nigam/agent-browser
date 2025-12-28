# Agent Prompt Recipes

## 1) Verify Form Validation
Use this to confirm required fields, error states, and success paths.
```text
You are testing form validation. Steps:
1) Go to <URL> and fill each required field with invalid data to trigger errors.
2) Capture the error message text, field name, and whether focus/aria-invalid is set.
3) Retest with valid data and confirm the error clears and submission succeeds.
Return a JSON list of {field, invalid_input, error_text, focus_set, aria_invalid, success_after_fix}.
```

## 2) Test Mobile Responsiveness
Check layout integrity at small breakpoints.
```text
Load <URL> at 375px wide. For the home, product, and checkout pages:
- Take full-page screenshots.
- Note any horizontal scrolling, clipped text, or overlapping components.
Return findings as a table: page, issue, selector/description, screenshot_path.
```

## 3) Scrape Data to JSON
Extract structured info from a page or paginated list.
```text
Visit <URL>. For each item card:
- Capture title, price, rating, availability, and item URL.
- Follow pagination until no more pages.
Return JSON: [{title, price, rating, availability, url}]. Save raw HTML snippets only if parsing fails and include reason.
```

## 4) Broken Link Checker
Quickly scan for dead or redirected links.
```text
Starting at <URL>, crawl internal links up to depth 2 (same domain).
For each link, record status (200/301/404/etc), final URL, anchor text, and source page.
Return CSV-formatted text with headers: source_url, anchor_text, target_url, status, final_url.
Flag anything not 200/301 as BROKEN.
```

## 5) Multi-Step Checkout Screenshotting
Document each step of checkout with visuals and notes.
```text
Perform checkout on <URL> with test data (no purchase if real). Steps: cart -> address -> shipping -> payment -> review -> confirmation.
At each step, save a screenshot and capture key state (items/counts, totals, applied discounts, required fields).
Return a step-by-step report: step_name, observations, blockers, screenshot_path.
Abort if payment requires real card details and report the blocker.
```
