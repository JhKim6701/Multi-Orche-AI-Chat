# ADR-002: Host-installed Ollama default

- Status: Accepted
- Context: local GPU access and OS-native model management are primary.
- Decision: connect to host Ollama first; keep provider abstraction for future container mode.
