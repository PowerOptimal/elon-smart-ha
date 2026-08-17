# Default: list available recipes.
default:
    @just --list

# Create the test virtualenv and install the HA test harness.
setup:
    uv venv --python 3.14
    uv pip install -r requirements-test.txt

# Run the test suite.
test *args:
    .venv/bin/python -m pytest {{args}}

# Install integration on a Home Assistant host via scp + restart.
# Usage: just install <host> [user]
#   e.g. just install 192.168.11.12
#        just install ha.lan dave
install host user="root":
    scp -r custom_components/elon_water_heater {{user}}@{{host}}:/config/custom_components/
    ssh {{user}}@{{host}} 'ha core restart'

manifest := "custom_components/elon_water_heater/manifest.json"

# Print the current integration version from manifest.json.
version:
    @jq -r .version {{manifest}}

# Tag the current commit with v<version> read from manifest.json.
# Refuses to run on a dirty working tree.  Pushes are explicit; this only
# creates the tag locally.
tag:
    @test -z "$(git status --porcelain --untracked-files=no)" || (echo "Working tree dirty; commit first." && exit 1)
    git tag "v$(jq -r .version {{manifest}})"
    @echo "Tagged v$(jq -r .version {{manifest}}). Push with: git push --tags"
