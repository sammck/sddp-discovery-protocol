#!/bin/bash

set -eo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$( dirname "$BIN_DIR" )"

cd "$PROJECT_DIR"
GH_TOKEN="$(cat "$HOME/.private/github-semantic-versioning_token.txt")" semantic-release "$@"
