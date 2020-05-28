import sys

DEFAULT_PROTOCOL = 2

if sys.version_info.major == 3:
    # Helper functions and classes to make pickle backward-compatible with python2
    # pickles, covering as many cases as we know.
    import pickle
    from functools import partial

    # Vanilla implementation of the unpickler that we'll subclass.
    VanillaUnpickler = pickle._Unpickler

    # Here's our unpickler that overwrites "BUILD" opcode. It takes data from the
    # stack, and if it's a dict, converts all the keys from bytes to strings.
    class CompatUnpickler(VanillaUnpickler):
        def load_build(self):
            state = self.stack[-1]
            if isinstance(state, dict):
                new_state = {to_str(k): v for k, v in state.items()}
                self.stack[-1] = new_state
            VanillaUnpickler.load_build(self)

    # We also need to explicitly register our own handler in the dispatcher, because
    # otherwise a method of the superclass will be called
    CompatUnpickler.dispatch[pickle.BUILD[0]] = CompatUnpickler.load_build

    # Backward-compatible load and loads, that use "bytes" as a default encoding.
    compat_load = partial(pickle._load, encoding="bytes")
    compat_loads = partial(pickle._loads, encoding="bytes")

    # Backward-compatible dump and dumps, that use the second version of the protocol.
    def compat_dump(obj, file, protocol=None, fix_imports=True, buffer_callback=None):
        return pickle._dump(
            obj,
            file,
            protocol=DEFAULT_PROTOCOL,
            fix_imports=fix_imports,
            buffer_callback=buffer_callback,
        )

    def compat_dumps(obj, protocol=None, fix_imports=True, buffer_callback=None):
        return pickle._dumps(
            obj,
            protocol=DEFAULT_PROTOCOL,
            fix_imports=fix_imports,
            buffer_callback=buffer_callback,
        )

    def to_str(obj):
        """
        Helper function to convert bytes to string.

        We use ASCII encoding, because in the context when it's called, we don't expect
        anything that's not ascii-compatible, and we want to fail earily.
        """
        if isinstance(obj, bytes):
            return obj.decode("ASCII")
        return obj

    # Backward-compatible versions of functions and classes
    compat = {
        "Unpickler": CompatUnpickler,
        "load": compat_load,
        "loads": compat_loads,
        "dump": compat_dump,
        "dumps": compat_dumps,
    }

else:
    import new
    import pickle

    # Vanilla implementation of teh objects that we overwrite.
    VanillaUnpickler = pickle.Unpickler
    vanilla_dump = pickle.dump
    vanilla_dumps = pickle.dumps

    # Here's our unicker that knows how to process old classes.
    class CompatUnpickler(VanillaUnpickler):
        def load_newobj(self):
            cls = self.stack[-2]
            if type(cls) == new.classobj:
                self.stack.pop()  # args
                cls = self.stack.pop()
                obj = new.instance(cls)
                self.append(obj)
            else:
                VanillaUnpickler.load_newobj(self)

    # We also need to explicitly register our own handler in the dispatcher, because
    # otherwise a method of the superclass will be called
    CompatUnpickler.dispatch[pickle.NEWOBJ] = CompatUnpickler.load_newobj

    # Forward-compatible load and loads, nothing is needed to be patched
    compat_load = pickle.load
    compat_loads = pickle.loads

    # Forward-compatible dump and dumps, that use the second version of the protocol.
    def compat_dump(obj, file, protocol=None):
        return vanilla_dump(obj, file, protocol=DEFAULT_PROTOCOL)

    def compat_dumps(obj, protocol=None):
        return vanilla_dumps(obj, protocol=DEFAULT_PROTOCOL)

    # Backward-compatible versions of functions and classes
    compat = {
        "Unpickler": CompatUnpickler,
        "load": compat_load,
        "loads": compat_loads,
        "dump": compat_dump,
        "dumps": compat_dumps,
    }

patched = False
orig = {
    "Unpickler": None,
    "load": None,
    "loads": None,
    "dump": None,
    "dumps": None,
}


def patch():
    """Replace Unpickler, load and loads with backward-compatible versions."""
    global patched, orig
    if patched:
        return

    for key, value in compat.items():
        orig[key] = getattr(pickle, key)
        setattr(pickle, key, value)

    patched = True


def unpatch():
    """Remove backward-compatible implementations."""
    global patched, orig
    if not patched:
        return

    for key, value in orig.items():
        setattr(pickle, key, value)

    patched = False
