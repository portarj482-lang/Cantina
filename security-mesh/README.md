# Security Mesh workspace folders

This folder contains two separate Security Mesh applications; they are not interchangeable.

- `security-mesh/` (this directory) is the older prototype. Its package and tests describe that implementation.
- `security-mesh/security-mesh/` is the fuller, actively developed application and its README is the primary product guide. Make application changes there unless a task explicitly targets the prototype.

Run commands from the specific package directory. Do not combine dependencies, generated output, or test results across the two package roots.
