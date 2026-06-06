from prometheus_client import REGISTRY

# We expose REGISTRY so tests and middleware can access the global registry
registry = REGISTRY
