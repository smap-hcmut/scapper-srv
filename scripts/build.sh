#!/bin/bash

# SMAP Scapper Service - Build and Push to Harbor Registry
# Usage: ./scripts/build.sh [build-push|login|help]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REGISTRY="${HARBOR_REGISTRY:-registry.tantai.dev}"
HARBOR_USER="${HARBOR_USERNAME:?HARBOR_USERNAME is not set}"
HARBOR_PASS="${HARBOR_PASSWORD:?HARBOR_PASSWORD is not set}"
PROJECT="smap"
SERVICE="scapper-srv"
DOCKERFILE="Dockerfile"
PLATFORM="${PLATFORM:-linux/amd64}"

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
err()     { echo -e "${RED}[ERROR]${NC} $1"; }

generate_tag() { date +"%y%m%d-%H%M%S"; }

image_name() {
    local tag="${1:-$(generate_tag)}"
    echo "${REGISTRY}/${PROJECT}/${SERVICE}:${tag}"
}

login() {
    info "Logging into Harbor registry: $REGISTRY"
    echo "$HARBOR_PASS" | docker login "$REGISTRY" -u "$HARBOR_USER" --password-stdin
    success "Logged in to $REGISTRY"
}

check_prereqs() {
    command -v docker &>/dev/null || { err "Docker not installed"; exit 1; }
    docker buildx version &>/dev/null || { err "Docker buildx not available"; exit 1; }
    [ -f "$DOCKERFILE" ] || { err "Dockerfile not found: $DOCKERFILE"; exit 1; }
}

build_and_push() {
    check_prereqs
    login

    local tag
    tag=$(generate_tag)
    local img
    img=$(image_name "$tag")
    local latest
    latest=$(image_name "latest")

    info "Registry:   $REGISTRY"
    info "Image:      $img"
    info "Platform:   $PLATFORM"
    info "Dockerfile: $DOCKERFILE"
    echo ""

    docker buildx build \
        --platform "$PLATFORM" \
        --provenance=false \
        --sbom=false \
        --tag "$img" \
        --tag "$latest" \
        --file "$DOCKERFILE" \
        --push \
        .

    echo ""
    success "Pushed: $img"
    success "Pushed: $latest"
    echo ""
    echo "Update deployments with: $img"
}

show_help() {
    cat <<EOF
${GREEN}SMAP Scapper - Build & Push (Harbor Registry)${NC}

Usage: $0 [command]

Commands:
    build-push   Build and push image to Harbor (default)
    login        Login to Harbor registry
    help         Show this help

Environment Variables:
    HARBOR_REGISTRY   Registry URL     (default: registry.tantai.dev)
    HARBOR_USERNAME   Registry user    (required)
    HARBOR_PASSWORD   Registry pass    (required)
    PLATFORM          Target platform  (default: linux/amd64)
EOF
}

case "${1:-build-push}" in
    build-push)  build_and_push ;;
    login)       login ;;
    help|--help|-h) show_help ;;
    *)
        err "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
