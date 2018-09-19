export PATH := /snap/bin:$(PATH)
export CHARM_NAME := sentry
export CHARM_STORE_GROUP := omnivector
export CHARM_BUILD_DIR := ./builds
export CHARM_DEPS_DIR := ./deps
export CHARM_PUSH_RESULT := charm-store-push-result.txt

# TARGETS
lint: ## Run linter
	@tox -e flake8
	@tox -e pycodestyle

build: clean ## Build charm
	@charm build ./src --log-level INFO --output-dir .

deploy: build ## Deploy charm 
	juju deploy $(CHARM_BUILD_DIR)/$(CHARM_NAME)

push: build ## Push and release charm to edge channel on charm store
	# See bug for why we can't push straight to edge
	# https://github.com/juju/charmstore-client/issues/146
	charm push $(CHARM_BUILD_DIR)/$(CHARM_NAME) cs:~$(CHARM_STORE_GROUP)/$(CHARM_NAME) > $(CHARM_PUSH_RESULT)
	cat $(CHARM_PUSH_RESULT)
	#awk 'NR==1{print $$2}' $(CHARM_PUSH_RESULT) | xargs -I{} charm release {} --channel edge

clean: ## Remove .tox and build dirs
	rm -rf .tox/
	rm -rf $(CHARM_BUILD_DIR)
	rm -rf $(CHARM_DEPS_DIR)
	rm -rf $(CHARM_PUSH_RESULT)


# Display target comments in 'make help'
help: 
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# SETTINGS
# Use one shell for all commands in a target recipe
.ONESHELL:
# Set default goal
.DEFAULT_GOAL := help
# Use bash shell in Make instead of sh 
SHELL := /bin/bash
