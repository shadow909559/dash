export const config = {
  version: import.meta.env.VITE_DASH_VERSION || "1.0.0",
  downloadUrl:
    import.meta.env.VITE_DASH_DOWNLOAD_URL ||
    "https://github.com/shadow909559/dash/releases/latest",
  releaseUrl:
    import.meta.env.VITE_DASH_RELEASE_URL ||
    "https://github.com/shadow909559/dash/releases",
  docsUrl:
    import.meta.env.VITE_DASH_DOCS_URL ||
    "https://github.com/shadow909559/dash/blob/main/DASH_REPORT.md",
  apiUrl: import.meta.env.VITE_DASH_API_URL || "",
  androidUrl:
    import.meta.env.VITE_DASH_ANDROID_URL ||
    "https://github.com/shadow909559/dash/releases/download/v1.0.0/DASH-v1.0.0.apk",
  repoUrl: "https://github.com/shadow909559/dash",
  issuesUrl: "https://github.com/shadow909559/dash/issues",
} as const;
