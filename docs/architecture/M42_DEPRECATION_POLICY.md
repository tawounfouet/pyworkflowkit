# Compatibility Policy — M42 Addendum

## Deprecation contract

A stable-intent deprecation carries subject, kind, since, planned removal, replacement
when available, and optional reason.

Normal removal must target at least the next minor release line:

~~~text
0.7.x -> 0.8.x or later
0.9.x -> 1.0.x or later
1.2.x -> 1.3.x or later
~~~

An emergency earlier target is allowed only with a concrete reason tied to security or
invariant correctness.

Warnings inherit from FutureWarning so application and adapter authors see migration
guidance under normal execution. One DeprecationEmitter warns once per identity:

~~~text
kind + subject + since + removal
~~~

ACTIVE_DEPRECATIONS is the shipped inventory. M42 introduces the mechanism with an empty
catalog; no existing API is deprecated simply to exercise the mechanism.
