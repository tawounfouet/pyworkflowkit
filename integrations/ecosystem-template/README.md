# PyWorkflowKit ecosystem integration template

This directory is a minimal independently packaged integration that uses only the public
`pyworkflowkit.ecosystem` SDK facade.

It demonstrates the complete author flow:

~~~text
choose PluginType
    ↓
implement public protocol
    ↓
plugin_registration(...)
    ↓
declare frozen entry-point group
    ↓
build wheel
    ↓
install next to PyWorkflowKit
    ↓
discover explicitly
    ↓
run conformance
~~~

The template intentionally contains no imports from:

~~~text
pyworkflowkit.application
pyworkflowkit.adapters
pyworkflowkit.domain
pyworkflowkit.plugins
pyworkflowkit.ports
~~~

Those lower-level dedicated surfaces remain available where documented, but the template
proves a normal integration author can stay on the consolidated SDK facade.
