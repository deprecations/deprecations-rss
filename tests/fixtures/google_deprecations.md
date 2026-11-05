> ## AI Agent Context
> Get the complete documentation index at: https://aistudio.google.com/llms.txt
> Use this file to discover all available pages.
> For the full documentation in a single file, fetch: https://aistudio.google.com/llms-full.txt

# Gemini deprecations

This page lists the known deprecation schedules for [stable
(GA)](/docs/models#stable) and [preview](/docs/models#preview) models and for
managed agents in the Gemini API. A "**deprecation**" is the announcement that
we no longer provide support for a model, and that it will be "**shut down**" in
the near future. Once a model is "**shutdown**", it is completely turned off, and
the endpoint is no longer available.

Deprecation announcements are made on the [Release notes](/docs/changelog) page,
and the announced earliest shutdown dates are tracked on this page.
Already-shutdown models and agents are listed under the **Deprecated models**
and **Deprecated agents** sections.

{% callout type="note" %}
  Note: The **shutdown dates listed in the table indicate the *earliest possible
  dates* on which a model might be retired**. We will communicate the exact
  shutdown date to users with advance notice to ensure a smooth transition to a
  replacement model.

{% /callout %}

## Gemini 3 models  {% id="gemini-3-models" %}

{% table %}
  * Model
  * Release date
  * Shutdown date
  * Recommended replacement

  ---

  * `gemini-3.8-flash-tts`
  * September 22, 2026
  * No shutdown date announced
  * 

  ---

  * `gemini-3.8-flash-lite-tts`
  * September 22, 2026
  * No shutdown date announced
  * 


  ---

  * `gemini-3.7-flash`
  * August 13, 2026
  * N/A
  * `gemini-3.8-flash` (`gemini-3.7-flash` is no longer available in Google AI Studio; the endpoint is not shutting down and automatically routes API requests to `gemini-3.8-flash`)

  ---

{% /table %}

## Gemini 2.5 Pro models  {% id="gemini-2.5-pro-models" %}

{% callout type="caution" %}
  `gemini-2.5-pro` is deprecated and is no longer available to select in Google AI
  Studio. Access through the API is limited to existing users who have actively
  used it in the past. Effective December 1, 2026, all API requests to
  `gemini-2.5-pro` will automatically route to
  [`gemini-3.8-flash`](/docs/models/gemini-3.8-flash) and be billed at
  [Gemini 3.8 Flash rates](/docs/pricing#gemini-3.8-flash). Review the breaking
  API changes in the
  [Gemini 3.8 Flash migration guide](/docs/whats-new-gemini-3.8#migrate-to-gemini-3-8-flash)
  before December 1, 2026.

{% /callout %}

{% table %}
  * Model
  * Release date
  * Shutdown date
  * Recommended replacement

  ---

  * `gemini-2.5-pro`
  * June 17, 2025
  * December 1, 2026
  * `gemini-3.8-flash` (`gemini-2.5-pro` is no longer available in Google AI Studio; effective December 1, 2026, API requests to `gemini-2.5-pro` will automatically route to `gemini-3.8-flash`)
{% /table %}

### Deprecated models  {% id="gemini-2.5-pro-deprecated-models" %}

{% table %}
  * Model
  * Release date
  * Shutdown date
  * Recommended replacement

  ---

  * `gemini-2.5-computer-use-preview-10-2025`
  * October 7, 2025
  * July 28, 2026
  * `gemini-3.8-flash`

  ---

  * `gemini-2.5-pro-preview-03-25`
  * March 3, 2025
  * December 2, 2025
  * `gemini-3.8-flash`

  ---

  * `gemini-2.5-pro-preview-05-06`
  * May 6, 2025
  * December 2, 2025
  * `gemini-3.8-flash`

  ---

  * `gemini-2.5-pro-preview-06-05`
  * June 5, 2025
  * December 2, 2025
  * `gemini-3.8-flash`
{% /table %}

