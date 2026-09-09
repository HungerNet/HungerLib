from .exceptions import RenamedMethodError, RemovedMethodError
from types import SimpleNamespace


def _make_removed_stub(method_name):
    def stub(*args, **kwargs):
        raise RemovedMethodError(f"The method '{method_name}' has been removed.")
    return stub


def _make_renamed_stub(old_name, new_name):
    def stub(*args, **kwargs):
        raise RenamedMethodError(
            f"The method '{old_name}' has been renamed. Please use '{new_name}' instead."
        )
    return stub


def proxy_method(method):
    '''Expose a bound method on its instance under its original name.'''
    obj = method.__self__
    name = method.__name__
    setattr(obj, name, method)


def rename_method(method, new_name, stub=None):
    '''Rename a bound method on an instance and shadow the old name with a stub.'''
    obj = method.__self__
    old_name = method.__name__

    setattr(obj, new_name, method)
    setattr(obj, old_name, stub or _make_renamed_stub(old_name, new_name))


def remove_method(method):
    '''Remove a bound method by shadowing it with a RemovedMethodError stub.'''
    obj = method.__self__
    old_name = method.__name__
    setattr(obj, old_name, _make_removed_stub(old_name))


def alias_method(method, new_name):
    '''Create an additional name for a bound method without removing the original.'''
    obj = method.__self__
    setattr(obj, new_name, method)


def bind_method(obj, func, name=None):
    '''Bind an external function as a method on an instance.'''
    setattr(obj, name or func.__name__, func.__get__(obj, obj.__class__))



methods = SimpleNamespace(
    rename=proxy_method,
    remove=remove_method,
    alias=alias_method,
    bind=bind_method,
    proxy=proxy_method,
)
