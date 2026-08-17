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

# Requires rsync on the HA host.  --delete removes files dropped from the
# repo, which scp could not do; the trailing slashes keep the copy in place
# rather than nesting a second directory inside it.
# Usage: just install <host> [user]
#   e.g. just install 192.168.11.12
#        just install ha.lan
[doc("Install the integration on a Home Assistant host and restart it")]
install host user="root":
    rsync -a --delete --exclude __pycache__ \
        custom_components/elon_water_heater/ \
        {{user}}@{{host}}:/config/custom_components/elon_water_heater/
    ssh {{user}}@{{host}} 'ha core restart'

manifest := "custom_components/elon_water_heater/manifest.json"

# Print the current integration version from manifest.json.
version:
    @jq -r .version {{manifest}}

# Refuses to run on a dirty working tree.  Pushes are explicit; this only
# creates the tag locally.
[doc("Tag the current commit with v<version> read from manifest.json")]
tag:
    @test -z "$(git status --porcelain --untracked-files=no)" || (echo "Working tree dirty; commit first." && exit 1)
    git tag "v$(jq -r .version {{manifest}})"
    @echo "Tagged v$(jq -r .version {{manifest}}). Push with: git push --tags"
