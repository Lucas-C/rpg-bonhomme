#!/bin/bash
set -o pipefail -o errexit -o nounset -o xtrace

cd $(dirname $(readlink -f "${BASH_SOURCE[0]}"))

pew in rpg-bonhomme make

