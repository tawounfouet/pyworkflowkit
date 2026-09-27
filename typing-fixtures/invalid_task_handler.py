"""This fixture must fail strict static typing under the RQ-03 contract."""

from pyworkflowkit import task


@task(id="invalid")
def invalid_task(left: int, right: int) -> int:
    return left + right
