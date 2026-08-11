# PR 8 validation

Production base: `25fb96e92bbd968c69abafb30b333a40011899f9` (`feature/07-config-versions`)

Production feature: `3da9a320e1e4c9e984fc168ebe2bf377d8458446` (`feature/08-workshop-library`)

The complete local fork gate passed on 2026-08-05:

- 108 cumulative unit/integration tests: pass;
- preview validates placement, incomplete collections, and hash conflicts before any file mutation: pass;
- arbitrary JSON rejection, scan depth/file/directory/time bounds, cached index reuse, and refresh timestamp: pass;
- identical content is idempotent; conflict policies stop, skip, retain a replacement backup, or choose a non-overwriting renamed destination: pass;
- mission files, metadata, DedicatedServerConfig, encrypted server metadata, config-version metadata, and audit are one compensated mutation: pass;
- injected later audit failure restores existing files and removes every newly created file/directory: pass;
- full rotations and unresolved conflicts leave mission files untouched: pass;
- incomplete collection application requires explicit acknowledgement and records missing IDs plus the decision in audit: pass;
- remote-member library and mutation surfaces are explicitly unavailable and do not show coordinator-local content: pass;
- durable Workshop refresh invalidates and rebuilds the bounded cache and returns the last refresh time: pass;
- strict Ruff, Mypy, ESLint, JavaScript type, stylelint, djLint, compile, secret, stack, and production/review identity gates: pass;
- desktop and mobile Chromium: 16 assertions, four hashed captures, no console/page errors, and no horizontal overflow: pass.

Physical iOS Safari is pending because no device was available. Mobile Chromium emulation is evidence only and is not reported as Safari validation.
