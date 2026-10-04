# PyWorkflowKit 0.8 transverse qualification integrations

These distributions are release-qualification fixtures, not production plugins.

They exist to prove two mandatory 0.8 exit scenarios:

~~~text
B. third-party executor plugin
F. broken optional integration isolated from core
~~~

The executor fixture imports only the consolidated `pyworkflowkit.ecosystem` authoring
surface.

The broken optional fixture deliberately publishes an event entry point whose target
module does not exist. Discovery must remain side-effect-free, explicit enablement must
report a failed plugin, and core-only workflows must continue to execute successfully.
