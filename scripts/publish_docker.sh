#!/usr/bin/env bash

set -e

# Default registry if not provided
REGISTRY=${1:-"jjesus109/content-registry:content-orchestrator"}

# Ensure we're at the project root
cd "$(dirname "$0")/.."

echo "🚀 Starting Docker publish script..."

# 1. Read the current version from pyproject.toml
# The regex ensures we only grab the 'version = "x.y.z"' line correctly.
CURRENT_VERSION=$(grep -m 1 -oE '^version = "[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml | awk -F'"' '{print $2}')

if [ -z "$CURRENT_VERSION" ]; then
    echo "❌ Could not find current version in pyproject.toml"
    exit 1
fi
echo "🔹 Current version: $CURRENT_VERSION"

# 2. Find the last git tag to determine the range of commits
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$LAST_TAG" ]; then
    echo "⚠️  No previous git tag found. Checking all commits."
    COMMITS=$(git log --format=%B)
else
    echo "🔍 Analyzing commits since tag: $LAST_TAG"
    # Added error handling if there are no commits
    COMMITS=$(git log ${LAST_TAG}..HEAD --format=%B 2>/dev/null || echo "")
fi

# 3. Detect version bump type using Conventional Commits
# If no commits, default to not bumping, but we can assume patch if forced
BUMP_TYPE="patch"

if echo "$COMMITS" | grep -qE "(BREAKING CHANGE:|^[a-zA-Z]+!\([^)]+\)?:|^[a-zA-Z]+!:)"; then
    BUMP_TYPE="major"
elif echo "$COMMITS" | grep -qE "^feat(\([^)]+\))?:"; then
    BUMP_TYPE="minor"
fi

if [ -z "$COMMITS" ]; then
    echo "✅ No new commits since last release. Bumping patch anyway by default, or exit instead (edit script if needed)."
    BUMP_TYPE="patch"
fi

echo "📈 Detected bump type: $BUMP_TYPE"

# 4. Calculate the new version
# Handle splitting robustly on macOS
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

if [ "$BUMP_TYPE" == "major" ]; then
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
elif [ "$BUMP_TYPE" == "minor" ]; then
    MINOR=$((MINOR + 1))
    PATCH=0
else
    PATCH=$((PATCH + 1))
fi

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo "✨ Bumping to new version: $NEW_VERSION"

# 5. Update the pyproject.toml
# Support both GNU sed (Linux) and BSD sed (macOS)
if sed --version 2>/dev/null | grep -q GNU; then
    sed -i "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
    sed -i '' "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# Sync uv.lock with the new version
echo "🔒 Updating uv.lock..."
uv lock

# 6. Build the Docker image
IMAGE_TAG="$REGISTRY-$NEW_VERSION"

echo "🐳 Building Docker image: $IMAGE_TAG"
docker build -t "$IMAGE_TAG" .

# 7. Push to the registry
echo "☁️  Pushing to registry..."
docker push "$IMAGE_TAG"

# 8. Git operations: commit the bump and create a new tag
echo "📦 Creating git tag v$NEW_VERSION..."
git add pyproject.toml uv.lock
git commit -m "chore(release): bump version to $NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

echo ""
echo "✅ Done! To finalize the release:"
echo "   git push origin main --tags"
