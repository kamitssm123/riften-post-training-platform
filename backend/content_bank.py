"""
Topic-locked content bank for the synthetic trace corpus.

Every question and every response belongs to a named `Topic`. A topic is a
short thread of `Exchange`s: exchange 0 is how the topic is opened, and any
further exchanges are natural, on-topic follow-ups (e.g. "check disk usage"
-> "okay now restart it"). Within an exchange, `questions` are paraphrases
of the same intent and `answers` are interchangeable valid responses to
that intent -- any question variant may be paired with any answer variant
from the same exchange and the pairing will still be topically correct.

This is the fix for the generator's content-pairing bug: previously
questions and responses were drawn independently from flat pools, so a
question about exponential backoff could be answered with a CSV-to-JSON
conversion. Sampling here must always pick a Topic first, then draw the
question and answer from the same Exchange -- see generate_corpus.py.

Agentic topics additionally carry a `ToolSpec` per exchange describing the
tool call a trace for that exchange should make; `error_answers` are used
when that tool call is simulated as failing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args: dict[str, Any]
    success_output: str
    error_output: str = "internal error: upstream unavailable"


@dataclass(frozen=True)
class Exchange:
    questions: list[str]
    answers: list[str]
    tool: Optional[ToolSpec] = None
    error_answers: Optional[list[str]] = None


@dataclass(frozen=True)
class Topic:
    id: str
    agentic: bool
    exchanges: list[Exchange] = field(default_factory=list)


TOPICS: list[Topic] = [
    # ---- non-agentic topics -------------------------------------------------
    Topic(
        id="password_reset_api",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "How do I reset a user's password via the admin API?",
                    "What's the admin API call for resetting a user's password?",
                    "Is there an endpoint to force a password reset for a user?",
                    "How can I trigger a password reset from the admin side?",
                ],
                answers=[
                    "Call `POST /admin/users/{id}/reset-password` with a valid admin token. This invalidates the user's existing sessions and emails them a reset link.",
                    "Use the admin API's `POST /admin/users/{id}/reset-password` endpoint. It requires an admin-scoped token and immediately revokes active sessions before sending the reset email.",
                    "The admin password reset endpoint is `POST /admin/users/{id}/reset-password`. Once called, all of that user's sessions are invalidated and a reset-link email goes out automatically.",
                    "You can force a password reset by hitting `POST /admin/users/{id}/reset-password` with an admin token -- this both invalidates existing sessions and queues the reset email.",
                ],
            ),
            Exchange(
                questions=[
                    "What if the user says they never got the reset email?",
                    "The reset email doesn't seem to be arriving -- what should I check?",
                ],
                answers=[
                    "Check the admin API's `GET /admin/users/{id}/email-log` for delivery status -- most misses are the email landing in spam or an outdated address on the account.",
                    "First confirm the address on file is current, then check the delivery log; if the reset email shows as sent, it's almost always a spam-filter issue on the user's side.",
                ],
            ),
        ],
    ),
    Topic(
        id="webhook_timeout_debug",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Why is my webhook delivery failing with a timeout?",
                    "My webhook endpoint keeps timing out -- what's going on?",
                    "What causes webhook delivery timeouts and how do I fix them?",
                    "Webhooks are failing with a timeout error -- any idea why?",
                ],
                answers=[
                    "Your endpoint is likely taking longer than the 5-second delivery timeout. Move slow processing to a background job and return a 200 immediately on receipt.",
                    "Webhook deliveries time out after 5 seconds. If your handler does heavy work synchronously, acknowledge receipt with a fast 200 first and process the payload asynchronously.",
                    "This almost always means the receiving endpoint isn't responding within the 5-second webhook timeout window -- offload the actual processing and return 200 right away.",
                    "The webhook delivery system gives your endpoint 5 seconds to respond. Anything slower gets marked a timeout, so decouple the response from the processing work.",
                ],
            ),
            Exchange(
                questions=[
                    "How many times will a timed-out webhook retry?",
                    "Does the webhook system retry after a timeout, and how often?",
                ],
                answers=[
                    "Timed-out webhook deliveries retry up to 5 times with exponential backoff before being marked permanently failed.",
                    "After a timeout, the webhook is retried up to 5 times with increasing delays between attempts.",
                ],
            ),
        ],
    ),
    Topic(
        id="sync_vs_async_modes",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "What's the difference between the `sync` and `async` client modes?",
                    "When should I use sync mode versus async mode in the client?",
                    "Can you explain sync vs async client modes?",
                    "How do the client's sync and async modes differ?",
                ],
                answers=[
                    "`sync` mode blocks until the response is fully received; `async` mode returns a future/promise you can await, which is useful for concurrent requests.",
                    "In `sync` mode the client call blocks the thread until the response comes back. `async` mode instead returns an awaitable immediately, letting you run multiple requests concurrently.",
                    "The `sync` client waits for each response before returning; the `async` client returns a promise right away so your code can await it while doing other work.",
                    "Choose `sync` when you just need a simple blocking call; choose `async` when you need to issue several client requests concurrently without blocking the thread.",
                ],
            ),
        ],
    ),
    Topic(
        id="changelog_summary",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Can you summarize this changelog entry for release notes?",
                    "Turn this changelog entry into something I can put in the release notes.",
                    "Summarize the changelog for our release notes, please.",
                    "What's a good release-notes summary for this changelog entry?",
                ],
                answers=[
                    "Added rate-limit headers to all API responses, fixed a race condition in session refresh, and deprecated the v1 `/search` endpoint in favor of v2.",
                    "For release notes: rate-limit headers now ship on every API response, a session-refresh race condition is fixed, and the v1 `/search` endpoint is deprecated in favor of v2.",
                    "This changelog entry covers three things worth calling out in release notes: new rate-limit headers on all responses, a session-refresh race-condition fix, and v1 `/search` deprecation in favor of v2.",
                    "Release notes summary: rate-limit headers added API-wide, a session-refresh race condition resolved, and the older v1 `/search` endpoint deprecated in favor of v2.",
                ],
            ),
        ],
    ),
    Topic(
        id="pagination_cursor",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "How do I paginate through a large export?",
                    "What's the right way to page through a big export result?",
                    "How does cursor-based pagination work for exports?",
                    "My export is too large for one page -- how do I paginate it?",
                ],
                answers=[
                    "Use the `cursor` field returned in each page's response and pass it as `?cursor=...` on the next request until the field is null.",
                    "Each export page returns a `cursor` value -- pass that back as the `cursor` query parameter to fetch the next page, and stop once it comes back null.",
                    "Exports are cursor-paginated: read the `cursor` from the response and include it on your next request; a null `cursor` means you've reached the last page.",
                    "Follow the `cursor` field in each page of the export response, passing it as `?cursor=...` on subsequent calls, until the API returns a null cursor.",
                ],
            ),
            Exchange(
                questions=[
                    "Can I paginate backwards to a previous page?",
                    "Is there a way to go back a page using the cursor?",
                ],
                answers=[
                    "The cursor is forward-only; to go back you'd need to have saved the previous page's cursor value yourself.",
                    "There's no reverse cursor -- paginating backwards means re-requesting from the start using a previously saved cursor.",
                ],
            ),
        ],
    ),
    Topic(
        id="regex_phone_validation",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Write a regex to validate US phone numbers.",
                    "Can you give me a regex for validating a US phone number?",
                    "What regex pattern matches US phone number formats?",
                    "I need a regex that validates US phone numbers with optional separators.",
                ],
                answers=[
                    "`^\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$` matches common US phone number formats with optional separators like dashes, dots, or a leading area-code parenthesis.",
                    "This pattern works for US phone numbers: `^\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$` -- it allows an optional parenthesized area code and optional dash/dot/space separators.",
                    "Use `^\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$` to validate US phone numbers; it accepts formats like (555) 123-4567, 555-123-4567, and 5551234567.",
                    "A solid US phone number regex is `^\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$`, covering the common separator styles people actually type.",
                ],
            ),
        ],
    ),
    Topic(
        id="apology_email_billing",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Draft a short apology email for a billing overcharge.",
                    "Can you write a quick apology email about a billing mistake?",
                    "I need an email apologizing for an overcharge on someone's invoice.",
                    "Write an apology email for a customer who was overcharged.",
                ],
                answers=[
                    "Subject: We're sorry about the billing error\\n\\nHi there, we identified an overcharge on your last invoice and have issued a full refund, which should post within 3-5 business days.",
                    "Subject: Apology for your recent billing overcharge\\n\\nHi, we found a billing error on your account that led to an overcharge, and we've already refunded the difference in full -- it should show up within 3-5 business days.",
                    "Subject: Billing correction and apology\\n\\nHi there, we're sorry -- your last invoice included an overcharge. We've refunded the full amount, and it should post to your original payment method in 3-5 business days.",
                    "Subject: We made a billing mistake -- here's the fix\\n\\nHi, apologies for the overcharge on your recent invoice. A full refund has been issued and should arrive within 3-5 business days.",
                ],
            ),
        ],
    ),
    Topic(
        id="exponential_backoff_explain",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Explain exponential backoff in one paragraph.",
                    "What is exponential backoff and why is it used?",
                    "Can you explain how exponential backoff retry logic works?",
                    "Give me a quick explanation of exponential backoff.",
                ],
                answers=[
                    "Exponential backoff retries a failed request with progressively longer delays (e.g. 1s, 2s, 4s, 8s), often with jitter, to avoid overwhelming a struggling service.",
                    "Exponential backoff is a retry strategy where each failed attempt waits longer than the last -- typically doubling the delay each time -- with random jitter added so retries don't all collide.",
                    "With exponential backoff, retry delays grow exponentially (1s, 2s, 4s, 8s...) instead of retrying immediately, which gives an overloaded service room to recover; jitter is usually added to spread out retries.",
                    "Exponential backoff means waiting progressively longer between retries after a failure -- doubling the delay each time and adding jitter -- so a struggling downstream service isn't hit with a retry storm.",
                ],
            ),
            Exchange(
                questions=[
                    "How many retries should I cap exponential backoff at?",
                    "What's a reasonable max retry count for exponential backoff?",
                ],
                answers=[
                    "A common cap is 5-6 attempts -- beyond that, the delays get long enough that you should surface the failure instead of retrying further.",
                    "Most implementations cap exponential backoff at around 5 retries; after that the request should fail loudly rather than keep waiting.",
                ],
            ),
        ],
    ),
    Topic(
        id="rate_limit_status_code",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "What status code should I return for a rate-limited request?",
                    "Which HTTP status code indicates a client has been rate limited?",
                    "What's the correct response code when I'm throttling a request?",
                    "How should a rate-limited API response be coded?",
                ],
                answers=[
                    "Return `429 Too Many Requests`, ideally with a `Retry-After` header indicating when the client can try again.",
                    "The standard response for a rate-limited request is `429 Too Many Requests`, paired with a `Retry-After` header so the client knows how long to wait.",
                    "Use `429 Too Many Requests` -- include a `Retry-After` header telling the client exactly when it's safe to retry.",
                    "A throttled request should get `429 Too Many Requests` with a `Retry-After` header rather than a generic 4xx or 5xx.",
                ],
            ),
        ],
    ),
    Topic(
        id="csv_to_json_convert",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Convert this CSV row into a JSON object for me.",
                    "Can you turn this CSV data into JSON?",
                    "How do I map a CSV row to a JSON object?",
                    "Help me convert CSV rows into JSON format.",
                ],
                answers=[
                    "Given the header row and values, here's the resulting JSON object with each column mapped to its corresponding field.",
                    "Match each CSV header to its value in the row and you get a JSON object where every column becomes a key-value field.",
                    "To convert a CSV row to JSON, pair each header-row column name with the value in that same position, producing one JSON object per row.",
                    "Here's the CSV row as JSON: each column from the header becomes a key, and each corresponding cell value becomes that key's field value.",
                ],
            ),
        ],
    ),
    Topic(
        id="sql_duplicate_rows_debug",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Debug why this SQL query returns duplicate rows.",
                    "My SQL query is returning duplicate rows -- what's wrong?",
                    "Why does this join produce duplicate results?",
                    "Can you help me figure out why this query has duplicate rows?",
                ],
                answers=[
                    "The join against the `orders` table is one-to-many without aggregation, so each matching order row duplicates the parent record. Add a `GROUP BY` or use a window function.",
                    "This is a classic one-to-many join issue: joining against `orders` without aggregating multiplies the parent row once per matching order. Add a `GROUP BY` (or dedupe with `ROW_NUMBER()`).",
                    "Duplicate rows here come from an unaggregated one-to-many join with `orders` -- each order match repeats the base row. Fix it with `GROUP BY` or a window function to collapse the duplicates.",
                    "The query duplicates rows because the join fans out one-to-many against `orders` with no aggregation. Adding `GROUP BY` on the primary key resolves it.",
                ],
            ),
            Exchange(
                questions=[
                    "Would a window function be better than GROUP BY here?",
                    "Should I use ROW_NUMBER() instead of GROUP BY to fix this?",
                ],
                answers=[
                    "A window function like ROW_NUMBER() partitioned by the parent id works well when you need to keep one specific row (e.g. the latest order) rather than aggregate values.",
                    "Use ROW_NUMBER() over GROUP BY when you want to pick a single representative row per group instead of collapsing values with an aggregate.",
                ],
            ),
        ],
    ),
    Topic(
        id="cron_expression_weekday",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Help me write a cron expression for every weekday at 9am.",
                    "What's the cron syntax for 9am on weekdays only?",
                    "I need a cron schedule that runs at 9am, Monday through Friday.",
                    "Can you write a cron expression that fires weekdays at 9 AM?",
                ],
                answers=[
                    "`0 9 * * 1-5` runs at 9:00 AM Monday through Friday.",
                    "Use `0 9 * * 1-5` -- that fires at 9:00 AM on weekdays only, skipping Saturday and Sunday.",
                    "The cron expression `0 9 * * 1-5` schedules the job for 9:00 AM every weekday, Monday through Friday.",
                    "`0 9 * * 1-5` is what you want: minute 0, hour 9, every day-of-month, every month, weekdays 1-5 (Mon-Fri).",
                ],
            ),
        ],
    ),
    Topic(
        id="caching_cache_control",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "How should I set Cache-Control headers for this API response?",
                    "What Cache-Control settings should I use to avoid stale data?",
                    "How do I control caching behavior for an API endpoint?",
                    "What's the right caching header setup for a frequently-changing resource?",
                ],
                answers=[
                    "For data that changes often, use `Cache-Control: no-cache` so clients revalidate on every request instead of trusting a local copy; for stable data, set a `max-age` that matches how long staleness is acceptable.",
                    "Set `Cache-Control: max-age=<seconds>` for anything safe to serve stale for a bit, and `no-cache` (forcing revalidation) for endpoints where correctness matters more than speed.",
                    "Use a short `max-age` plus `stale-while-revalidate` for endpoints that tolerate brief staleness, or `no-store` entirely for responses that must never be cached.",
                    "Cache-Control should reflect how tolerant the data is of staleness: `max-age` for mostly-static responses, `no-cache` to force revalidation, `no-store` when caching would actually be wrong.",
                ],
            ),
            Exchange(
                questions=[
                    "What about Cache-Control for authenticated, user-specific responses?",
                    "Should user-specific API responses be cached at all?",
                ],
                answers=[
                    "User-specific responses should generally be `Cache-Control: private, no-store` or `private, max-age=<short>` -- never cached by a shared/proxy cache.",
                    "For authenticated responses, mark them `private` so only the user's own client can cache them, and keep any `max-age` short given the data can change per-request.",
                ],
            ),
        ],
    ),
    Topic(
        id="session_token_expiry",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "Why does the session token expire so quickly?",
                    "Users keep getting logged out -- is that expected session behavior?",
                    "What determines how long a session token stays valid?",
                    "Can you explain the session expiry / token refresh behavior?",
                ],
                answers=[
                    "Session tokens are short-lived by design -- typically 15-60 minutes -- and are meant to be silently refreshed via a refresh token before they expire; unexpected logouts usually mean the refresh call is failing.",
                    "The session token itself has a short expiry window and relies on a background refresh call to renew it; if that refresh request fails or is blocked, the user gets logged out even though the session was otherwise healthy.",
                    "Session tokens expire quickly on purpose for security, but the client should be silently exchanging the refresh token for a new one before that happens -- check whether refresh calls are actually succeeding.",
                    "Short session-token lifetimes are expected; the refresh token is what's supposed to keep the user logged in transparently. Frequent logouts point to the refresh flow failing, not the expiry itself being misconfigured.",
                ],
            ),
            Exchange(
                questions=[
                    "Should the refresh token itself expire at some point?",
                    "Does the refresh token ever need to expire, or does it last forever?",
                ],
                answers=[
                    "Yes -- refresh tokens should have their own (much longer) expiry, typically days to weeks, so a stolen token doesn't grant indefinite access.",
                    "Refresh tokens shouldn't be permanent; giving them a longer-but-bounded lifetime (days to weeks) limits the damage if one is ever compromised.",
                ],
            ),
        ],
    ),
    Topic(
        id="api_versioning_strategy",
        agentic=False,
        exchanges=[
            Exchange(
                questions=[
                    "What's a safe way to version this API without breaking existing clients?",
                    "How should I approach API versioning here?",
                    "What's the best practice for rolling out a breaking API change?",
                    "How do I introduce a new API version without breaking current integrations?",
                ],
                answers=[
                    "Introduce the change under a new version path (e.g. `/v2/...`) and keep `/v1/...` fully functional in parallel, giving existing clients a deprecation window before you sunset the old version.",
                    "Version the endpoint (`/v2/...`) rather than mutating `/v1/...` in place, so existing integrations keep working unchanged until you formally deprecate and eventually retire v1.",
                    "The safe pattern is additive versioning: ship the breaking change as `/v2/...`, leave `/v1/...` untouched, and communicate a clear deprecation timeline before removing v1.",
                    "Avoid breaking clients by putting the change behind a new API version path, running old and new versions side by side, and deprecating the old one only after clients have had time to migrate.",
                ],
            ),
        ],
    ),
    # ---- agentic topics -------------------------------------------------------
    Topic(
        id="order_lookup_refund",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Look up the current status of order #48213 and refund it if it's still pending.",
                    "Can you check order #48213 and issue a refund if it hasn't shipped yet?",
                    "What's the status of order #48213? Refund it if it's still pending.",
                    "Please check on order #48213 and refund it if it hasn't processed yet.",
                ],
                answers=[
                    "I checked order #48213 and it's still pending, so I've issued a full refund.",
                    "Order #48213 was still in pending status, so I went ahead and refunded it in full.",
                    "I looked up order #48213 -- it hadn't shipped yet, so I processed a full refund for it.",
                    "Order #48213 came back as pending, so I issued the refund right away.",
                ],
                tool=ToolSpec(
                    name="lookup_order",
                    args={"order_id": "48213"},
                    success_output="status: pending, refund issued: true",
                ),
                error_answers=[
                    "I attempted to look up order #48213 but the order-lookup service returned an error, so I wasn't able to confirm its status or issue a refund.",
                    "The lookup for order #48213 failed with a service error -- I couldn't retrieve its status, so no refund was issued yet.",
                ],
            ),
            Exchange(
                questions=[
                    "Can you email the customer to let them know about the refund?",
                    "Could you send the customer a quick note about the refund on order #48213?",
                ],
                answers=[
                    "I've emailed the customer confirming the refund for order #48213 and letting them know when to expect the funds.",
                    "Sent a note to the customer confirming order #48213 was refunded, including the expected refund timeline.",
                ],
                tool=ToolSpec(
                    name="send_customer_email",
                    args={"order_id": "48213"},
                    success_output="email sent: true",
                ),
                error_answers=[
                    "I tried to send the refund confirmation email for order #48213 but the email service failed, so the customer hasn't been notified yet.",
                ],
            ),
        ],
    ),
    Topic(
        id="disk_infra_ops",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Check disk usage on the prod-db-2 host and restart the service if it's above 90%.",
                    "Can you check prod-db-2's disk usage and restart the service if it's over 90%?",
                    "What's the disk usage on prod-db-2? Restart the service if it's critical (>90%).",
                    "Please check disk space on prod-db-2 and restart if usage is above 90%.",
                ],
                answers=[
                    "Disk usage on prod-db-2 is at 94%, so I restarted the service and cleared temp logs.",
                    "prod-db-2 was at 94% disk usage, above the 90% threshold, so I went ahead and restarted the service after clearing temp logs.",
                    "Checked prod-db-2 -- disk usage is 94%, over the limit, so I restarted the service and freed up space by clearing temp logs.",
                    "prod-db-2's disk usage came back at 94%. Since that's above 90%, I restarted the service and cleaned up temp logs.",
                ],
                tool=ToolSpec(
                    name="check_disk_usage",
                    args={"host": "prod-db-2"},
                    success_output="disk usage: 94%",
                ),
                error_answers=[
                    "I tried to check disk usage on prod-db-2 but the infra monitoring call failed, so I couldn't confirm usage or restart the service.",
                    "The disk-usage check for prod-db-2 returned an error -- I wasn't able to determine whether a restart was needed.",
                ],
            ),
            Exchange(
                questions=[
                    "Can you confirm disk usage is back to normal now?",
                    "Is prod-db-2 healthy again after the restart?",
                ],
                answers=[
                    "Re-checked prod-db-2 -- disk usage is back down to 41% after the restart and log cleanup.",
                    "prod-db-2 is healthy now: disk usage dropped to 41% following the restart.",
                ],
                tool=ToolSpec(
                    name="check_disk_usage",
                    args={"host": "prod-db-2"},
                    success_output="disk usage: 41%",
                ),
                error_answers=[
                    "I tried to re-check disk usage on prod-db-2 but the monitoring call failed, so I can't confirm it's back to normal yet.",
                ],
            ),
        ],
    ),
    Topic(
        id="customer_plan_change",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Find the customer record for jane@example.com and update their plan to Pro.",
                    "Can you look up jane@example.com and upgrade them to the Pro plan?",
                    "Please find jane@example.com's account and move them to Pro.",
                    "Upgrade jane@example.com to Pro -- can you find their record first?",
                ],
                answers=[
                    "Found the customer record and upgraded jane@example.com to the Pro plan.",
                    "jane@example.com's account is now on the Pro plan -- I located the record and applied the upgrade.",
                    "I found jane@example.com in the system and switched their plan to Pro.",
                    "jane@example.com has been upgraded to Pro; I pulled up their record and applied the change directly.",
                ],
                tool=ToolSpec(
                    name="lookup_customer",
                    args={"email": "jane@example.com"},
                    success_output="plan: Pro",
                ),
                error_answers=[
                    "I looked for jane@example.com but the customer-lookup service returned an error, so I couldn't apply the Pro upgrade.",
                    "The customer lookup for jane@example.com failed -- I wasn't able to confirm the account or change the plan.",
                ],
            ),
            Exchange(
                questions=[
                    "Does the Pro upgrade for jane@example.com take effect immediately?",
                    "When does jane@example.com's new plan actually kick in?",
                ],
                answers=[
                    "Yes -- jane@example.com's Pro plan is active immediately, no waiting period.",
                    "The upgrade for jane@example.com is already in effect; Pro features are available right now.",
                ],
                tool=ToolSpec(
                    name="lookup_customer",
                    args={"email": "jane@example.com"},
                    success_output="plan: Pro, effective: immediate",
                ),
                error_answers=[
                    "I tried to re-check jane@example.com's account but the lookup failed, so I can't confirm the effective date right now.",
                ],
            ),
        ],
    ),
    Topic(
        id="deploy_status_check",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Search recent deploys for the payments service and tell me if the last one succeeded.",
                    "Did the last deploy for the payments service succeed?",
                    "Can you check the payments service's recent deploys and confirm the last one went fine?",
                    "What's the status of the most recent payments service deploy?",
                ],
                answers=[
                    "The last deploy for the payments service completed successfully 2 hours ago.",
                    "Payments service's most recent deploy succeeded -- it went out about 2 hours ago with no errors.",
                    "Checked the deploy history for payments: the latest one finished successfully roughly 2 hours ago.",
                    "The payments service's last deploy was a success, completed 2 hours ago.",
                ],
                tool=ToolSpec(
                    name="search_deploys",
                    args={"service": "payments"},
                    success_output="last deploy: success, 2h ago",
                ),
                error_answers=[
                    "I tried to search deploys for the payments service but the deploy-history lookup failed, so I can't confirm the last deploy's status.",
                    "The deploy search for the payments service errored out -- I wasn't able to retrieve the recent deploy history.",
                ],
            ),
            Exchange(
                questions=[
                    "Were there any errors in that payments deploy's logs?",
                    "Anything concerning in the logs from the last payments deploy?",
                ],
                answers=[
                    "No errors in the logs for that deploy -- the payments service rollout was clean.",
                    "I checked the deploy logs and there were zero errors reported for that payments release.",
                ],
                tool=ToolSpec(
                    name="search_deploys",
                    args={"service": "payments"},
                    success_output="last deploy: success, 0 errors logged",
                ),
                error_answers=[
                    "I tried to pull the deploy logs for payments but the lookup failed, so I can't confirm whether there were errors.",
                ],
            ),
        ],
    ),
    Topic(
        id="log_triage_fetch",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Pull the latest error logs for the ingestion worker and summarize the top issue.",
                    "Can you check the ingestion worker's error logs and tell me what's going wrong?",
                    "What's the top recurring error in the ingestion worker's logs right now?",
                    "Please fetch recent logs for the ingestion worker and summarize the main problem.",
                ],
                answers=[
                    "The top recurring error is a connection timeout to the upstream queue, occurring roughly every 10 minutes.",
                    "Ingestion worker logs show one dominant issue: a connection timeout to the upstream queue, repeating about every 10 minutes.",
                    "The main problem in the ingestion worker's logs is a recurring connection timeout to the upstream message queue, roughly every 10 minutes.",
                    "Pulling the logs, the top error is the ingestion worker timing out connecting to the upstream queue, roughly every 10 minutes.",
                ],
                tool=ToolSpec(
                    name="fetch_logs",
                    args={"service": "ingestion-worker"},
                    success_output="top error: connection timeout to upstream queue, ~every 10min",
                ),
                error_answers=[
                    "I tried to fetch logs for the ingestion worker but the log service returned an error, so I couldn't retrieve or summarize anything.",
                    "The log fetch for the ingestion worker failed -- I don't have visibility into the current errors.",
                ],
            ),
            Exchange(
                questions=[
                    "Has that connection timeout been getting worse recently?",
                    "Is the ingestion worker's timeout issue trending up?",
                ],
                answers=[
                    "Yes -- the connection timeout frequency for the ingestion worker is up about 20% over the last 24 hours.",
                    "It's trending worse: timeouts on the ingestion worker have increased roughly 20% in the past day.",
                ],
                tool=ToolSpec(
                    name="fetch_logs",
                    args={"service": "ingestion-worker"},
                    success_output="timeout frequency: up 20% over last 24h",
                ),
                error_answers=[
                    "I tried to pull a trend on the ingestion worker's timeouts but the log service failed, so I can't confirm the trend right now.",
                ],
            ),
        ],
    ),
    Topic(
        id="webhook_delivery_check",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Can you check why webhook events aren't arriving for customer acme-corp?",
                    "Debug the webhook delivery issue for acme-corp -- nothing's coming through.",
                    "acme-corp says they're not receiving webhook events -- can you look into it?",
                    "Please check the webhook delivery log for acme-corp.",
                ],
                answers=[
                    "acme-corp's webhook endpoint is returning 404 on every recent delivery attempt -- the last 12 all failed. Their endpoint URL is likely misconfigured or has moved.",
                    "I checked acme-corp's delivery log: all 12 recent webhook attempts failed with a 404, which points to a wrong or outdated endpoint URL on their side.",
                    "The webhook deliveries for acme-corp are all hitting a 404 -- 12 for 12 recent attempts -- so their registered endpoint URL is probably no longer valid.",
                    "acme-corp's last 12 webhook deliveries all came back 404. That means the endpoint they've registered isn't resolving correctly anymore.",
                ],
                tool=ToolSpec(
                    name="check_webhook_deliveries",
                    args={"customer": "acme-corp"},
                    success_output="last 12 deliveries: all failed, endpoint returning 404",
                ),
                error_answers=[
                    "I tried to pull acme-corp's webhook delivery log but the lookup failed, so I couldn't confirm what's happening on their end.",
                    "The webhook delivery check for acme-corp errored out before returning any results.",
                ],
            ),
        ],
    ),
    Topic(
        id="incident_summary_lookup",
        agentic=True,
        exchanges=[
            Exchange(
                questions=[
                    "Look up incident INC-4471 and summarize what happened.",
                    "Can you pull up incident INC-4471 and give me a summary?",
                    "What happened during incident INC-4471?",
                    "Summarize incident INC-4471 for me.",
                ],
                answers=[
                    "Incident INC-4471 was caused by an expired TLS certificate on the internal gateway, which caused a 34-minute outage before it was rotated.",
                    "INC-4471: an expired TLS cert on the internal gateway broke internal traffic for about 34 minutes until the cert was renewed.",
                    "The root cause of INC-4471 was an expired TLS certificate on the internal gateway -- it took 34 minutes to detect and rotate the cert.",
                    "INC-4471 traces back to an expired TLS certificate on the internal gateway, resulting in roughly 34 minutes of impact before resolution.",
                ],
                tool=ToolSpec(
                    name="fetch_incident",
                    args={"incident_id": "INC-4471"},
                    success_output="cause: expired TLS cert on internal gateway, duration: 34min",
                ),
                error_answers=[
                    "I tried to pull up incident INC-4471 but the incident-tracking lookup failed, so I don't have the details yet.",
                    "The lookup for INC-4471 returned an error -- I wasn't able to retrieve the incident summary.",
                ],
            ),
        ],
    ),
]

NON_AGENTIC_TOPICS = [t for t in TOPICS if not t.agentic]
AGENTIC_TOPICS = [t for t in TOPICS if t.agentic]
