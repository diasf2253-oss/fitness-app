"""HTTP endpoints, one module per feature. Routers stay thin: validate the
request, scope by current_user.id, call services/, return a schema.
A router never imports another router — shared logic goes in services/."""
