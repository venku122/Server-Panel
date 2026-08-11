export default [
  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        alert: "readonly",
        Blob: "readonly",
        clearInterval: "readonly",
        confirm: "readonly",
        console: "readonly",
        CSS: "readonly",
        document: "readonly",
        Event: "readonly",
        fetch: "readonly",
        FileReader: "readonly",
        FormData: "readonly",
        localStorage: "readonly",
        location: "readonly",
        navigator: "readonly",
        prompt: "readonly",
        requestAnimationFrame: "readonly",
        setInterval: "readonly",
        setTimeout: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        window: "readonly"
      }
    },
    rules: {
      "no-dupe-args": "error",
      "no-redeclare": "error",
      "no-undef": "error",
      "no-unreachable": "error"
    }
  },
  {
    files: ["**/scripts/fork/*.cjs"],
    languageOptions: {
      globals: {
        process: "readonly",
        require: "readonly"
      }
    }
  }
];
