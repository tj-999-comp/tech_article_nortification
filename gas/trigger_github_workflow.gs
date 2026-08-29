/**
 * Trigger the Qiita notification workflow from Google Apps Script.
 *
 * Store GITHUB_TOKEN in Apps Script > Project Settings > Script properties.
 * Do not put a token in this source file or in a spreadsheet cell.
 */
const GITHUB_API_BASE_URL = "https://api.github.com";
const DEFAULT_REPOSITORY = "tj-999-comp/tech_article_nortification";
const DEFAULT_WORKFLOW = "daily-qiita-notify.yml";
const DEFAULT_REF = "main";
const MAX_ATTEMPTS = 3;

/**
 * Manual entry point. Run this function from the Apps Script editor.
 * @return {{repository: string, workflow: string, ref: string, status: number}}
 */
function triggerGitHubWorkflow() {
  const properties = PropertiesService.getScriptProperties();
  const token = properties.getProperty("GITHUB_TOKEN");
  if (!token) {
    throw new Error("Script property GITHUB_TOKEN is not set.");
  }

  const repository = properties.getProperty("GITHUB_REPOSITORY") || DEFAULT_REPOSITORY;
  const workflow = properties.getProperty("GITHUB_WORKFLOW") || DEFAULT_WORKFLOW;
  const ref = properties.getProperty("GITHUB_REF") || DEFAULT_REF;
  const endpoint = buildDispatchEndpoint_(repository, workflow);
  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    payload: JSON.stringify({ref: ref}),
    muteHttpExceptions: true,
  };

  let response;
  let lastError;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      response = UrlFetchApp.fetch(endpoint, options);
    } catch (error) {
      lastError = error;
      if (attempt < MAX_ATTEMPTS) {
        Utilities.sleep(retryDelayMilliseconds_(attempt));
        continue;
      }
      throw new Error("GitHub workflow dispatch failed: " + error.message);
    }

    const status = response.getResponseCode();
    if (status === 204) {
      return {
        repository: repository,
        workflow: workflow,
        ref: ref,
        status: status,
      };
    }

    if (!isRetryableStatus_(status) || attempt === MAX_ATTEMPTS) {
      // Do not include the response body: it is not needed for diagnosis and
      // avoids accidentally exposing information in Apps Script execution logs.
      throw new Error(
        "GitHub workflow dispatch failed with HTTP " + status +
        ". Check GITHUB_TOKEN permissions, workflow name, and ref."
      );
    }
    Utilities.sleep(retryDelayMilliseconds_(attempt));
  }

  throw new Error("GitHub workflow dispatch failed: " + (lastError || "unknown error"));
}

/** Entry point for a time-driven Apps Script trigger. */
function runScheduledWorkflow() {
  return triggerGitHubWorkflow();
}

/**
 * Install the Wednesday and Saturday 08:00 JST triggers used by this project.
 * Existing triggers for runScheduledWorkflow are removed first, so this is
 * safe to run again when changing the schedule.
 */
function installTimeTriggers() {
  const handler = "runScheduledWorkflow";
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === handler) {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  [ScriptApp.WeekDay.WEDNESDAY, ScriptApp.WeekDay.SATURDAY].forEach(function(day) {
    ScriptApp.newTrigger(handler)
      .timeBased()
      .onWeekDay(day)
      .atHour(8)
      .nearMinute(0)
      .inTimezone("Asia/Tokyo")
      .create();
  });
}

function buildDispatchEndpoint_(repository, workflow) {
  return GITHUB_API_BASE_URL + "/repos/" + repository +
    "/actions/workflows/" + encodeURIComponent(workflow) + "/dispatches";
}

function isRetryableStatus_(status) {
  return status === 408 || status === 429 || status >= 500;
}

function retryDelayMilliseconds_(attempt) {
  return attempt * 1000;
}
