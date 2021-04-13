#!/bin/bash
set -o pipefail -o errexit -o nounset -o xtrace

date

cd $(dirname $(readlink -f "${BASH_SOURCE[0]}"))

PATH=$PATH:/usr/local/bin/
pew in rpg-bonhomme make -B
