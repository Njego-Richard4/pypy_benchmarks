
from _ctypes.basics import _CData, _CDataMeta, cdata_from_address
from _ctypes.primitive import SimpleType, _SimpleCData
from _ctypes.basics import ArgumentError, keepalive_key
from _ctypes.basics import is_struct_shape
from _ctypes.builtin import get_errno, set_errno, get_last_error, set_last_error
import _rawffi
import _ffi
import sys
import traceback
import warnings

try: from __pypy__ import builtinify
except ImportError: builtinify = lambda f: f

# XXX this file needs huge refactoring I fear

PARAMFLAG_FIN   = 0x1
PARAMFLAG_FOUT  = 0x2
PARAMFLAG_FLCID = 0x4
PARAMFLAG_COMBINED = PARAMFLAG_FIN | PARAMFLAG_FOUT | PARAMFLAG_FLCID

VALID_PARAMFLAGS = (
    0,
    PARAMFLAG_FIN,
    PARAMFLAG_FIN | PARAMFLAG_FOUT,
    PARAMFLAG_FIN | PARAMFLAG_FLCID
    )

WIN64 = sys.platform == 'win32' and sys.maxint == 2**63 - 1


def get_com_error(errcode, riid, pIunk):
    "Win32 specific: build a COM Error exception"
    # XXX need C support code
    from _ctypes import COMError
    return COMError(errcode, None, None)

@builtinify
def call_function(func, args):
    "Only for debugging so far: So that we can call CFunction instances"
    funcptr = CFuncPtr(func)
    funcptr.restype = int
    return funcptr(*args)


class CFuncPtrType(_CDataMeta):
    # XXX write down here defaults and such things

    def _sizeofinstances(self):
        return _rawffi.sizeof('P')

    def _alignmentofinstances(self):
        return _rawffi.alignment('P')

    def _is_pointer_like(self):
        return True

    from_address = cdata_from_address


class CFuncPtr(_CData):
    __metaclass__ = CFuncPtrType

    _argtypes_ = None
    _restype_ = None
    _errcheck_ = None
    _flags_ = 0
    _ffiargshape = 'P'
    _ffishape = 'P'
    _fficompositesize = None
    _ffiarray = _rawffi.Array('P')
    _needs_free = False
    callable = None
    _ptr = None
    _buffer = None
    _address = None
    # win32 COM properties
    _paramflags = None
    _com_index = None
    _com_iid = None
    _is_fastpath = False

    def _getargtypes(self):
        return self._argtypes_

    def _setargtypes(self, argtypes):
        self._ptr = None
        if argtypes is None:
            self._argtypes_ = ()
        else:
            for i, argtype in enumerate(argtypes):
                if not hasattr(argtype, 'from_param'):
                    raise TypeError(
                        "item %d in _argtypes_ has no from_param method" % (
                            i + 1,))
            self._argtypes_ = list(argtypes)
            self._check_argtypes_for_fastpath()
    argtypes = property(_getargtypes, _setargtypes)

    def _check_argtypes_for_fastpath(self):
        if all([hasattr(argtype, '_ffiargshape') for argtype in self._argtypes_]):
            fastpath_cls = make_fastpath_subclass(self.__class__)
            fastpath_cls.enable_fastpath_maybe(self)

    def _getparamflags(self):
        return self._paramflags

    def _setparamflags(self, paramflags):
        if paramflags is None or not self._argtypes_:
            self._paramflags = None
            return
        if not isinstance(paramflags, tuple):
            raise TypeError("paramflags must be a tuple or None")
        if len(paramflags) != len(self._argtypes_):
            raise ValueError("paramflags must have the same length as argtypes")
        for idx, paramflag in enumerate(paramflags):
            paramlen = len(paramflag)
            name = default = None
            if paramlen == 1:
                flag = paramflag[0]
            elif paramlen == 2:
                flag, name = paramflag
            elif paramlen == 3:
                flag, name, default = paramflag
            else:
                raise TypeError(
                    "paramflags must be a sequence of (int [,string [,value]]) "
                    "tuples"
                    )
            if not isinstance(flag, int):
                raise TypeError(
                    "paramflags must be a sequence of (int [,string [,value]]) "
                    "tuples"
                    )
            _flag = flag & PARAMFLAG_COMBINED
            if _flag == PARAMFLAG_FOUT:
                typ = self._argtypes_[idx]
                if getattr(typ, '_ffiargshape', None) not in ('P', 'z', 'Z'):
                    raise TypeError(
                        "'out' parameter %d must be a pointer type, not %s"
                        % (idx+1, type(typ).__name__)
                        )
            elif _flag not in VALID_PARAMFLAGS:
                raise TypeError("paramflag value %d not supported" % flag)
        self._paramflags = paramflags

    paramflags = property(_getparamflags, _setparamflags)


    def _getrestype(self):
        return self._restype_

    def _setrestype(self, restype):
        self._ptr = None
        if restype is int:
            from ctypes import c_int
            restype = c_int
        if not (isinstance(restype, _CDataMeta) or restype is None or
                callable(restype)):
            raise TypeError("restype must be a type, a callable, or None")
        self._restype_ = restype

    def _delrestype(self):
        self._ptr = None
        del self._restype_

    restype = property(_getrestype, _setrestype, _delrestype)

    def _geterrcheck(self):
        return getattr(self, '_errcheck_', None)
    def _seterrcheck(self, errcheck):
        if not callable(errcheck):
            raise TypeError("The errcheck attribute must be callable")
        self._errcheck_ = errcheck
    def _delerrcheck(self):
        try:
            del self._errcheck_
        except AttributeError:
            pass
    errcheck = property(_geterrcheck, _seterrcheck, _delerrcheck)

    def _ffishapes(self, args, restype):
        if args is None:
            args = []
        argtypes = [arg._ffiargshape for arg in args]
        if restype is not None:
            if not isinstance(restype, SimpleType):
                raise TypeError("invalid result type for callback function")
            restype = restype._ffiargshape
        else:
            restype = 'O' # void
        return argtypes, restype

    def _set_address(self, address):
        if not self._buffer:
            self._buffer = _rawffi.Array('P')(1)
        self._buffer[0] = address

    def _get_address(self):
        return self._buffer[0]

    def __init__(self, *args):
        self.name = None
        self._objects = {keepalive_key(0):self}
        self._needs_free = True

        # Empty function object -- this is needed for casts
        if not args:
            self._set_address(0)
            return

        argsl = list(args)
        argument = argsl.pop(0)

        # Direct construction from raw address
        if isinstance(argument, (int, long)) and not argsl:
            self._set_address(argument)
            restype = self._restype_
            if restype is None:
                import ctypes
                restype = ctypes.c_int
            self._ptr = self._getfuncptr_fromaddress(self._argtypes_, restype)
            self._check_argtypes_for_fastpath()
            return


        # A callback into python
        if callable(argument) and not argsl:
            self.callable = argument
            ffiargs, ffires = self._ffishapes(self._argtypes_, self._restype_)
            if self._restype_ is None:
                ffires = None
            self._ptr = _rawffi.CallbackPtr(self._wrap_callable(argument,
                                                                self.argtypes),
                                            ffiargs, ffires, self._flags_)
            self._buffer = self._ptr.byptr()
            return

        # Function exported from a shared library
        if isinstance(argument, tuple) and len(argument) == 2:
            import ctypes
            self.name, dll = argument
            if isinstance(dll, str):
                self.dll = ctypes.CDLL(self.dll)
            else:
                self.dll = dll
            if argsl:
                self.paramflags = argsl.pop(0)
                if argsl:
                    raise TypeError("Unknown constructor %s" % (args,))
            # We need to check dll anyway
            ptr = self._getfuncptr([], ctypes.c_int)
            self._set_address(ptr.getaddr())
            return

        # A COM function call, by index
        if (sys.platform == 'win32' and isinstance(argument, (int, long))
            and argsl):
            ffiargs, ffires = self._ffishapes(self._argtypes_, self._restype_)
            self._com_index =  argument + 0x1000
            self.name = argsl.pop(0)
            if argsl:
                self.paramflags = argsl.pop(0)
                if argsl:
                    self._com_iid = argsl.pop(0)
                    if argsl:
                        raise TypeError("Unknown constructor %s" % (args,))
            return

        raise TypeError("Unknown constructor %s" % (args,))

    def _wrap_callable(self, to_call, argtypes):
        def f(*args):
            if argtypes:
                args = [argtype._CData_retval(argtype.from_address(arg)._buffer)
                        for argtype, arg in zip(argtypes, args)]
            return to_call(*args)
        return f

    def __call__(self, *args, **kwargs):
        argtypes = self._argtypes_
        if self.callable is not None:
            if len(args) == len(argtypes):
                pass
            elif self._flags_ & _rawffi.FUNCFLAG_CDECL:
                if len(args) < len(argtypes):
                    plural = len(argtypes) > 1 and "s" or ""
                    raise TypeError(
                        "This function takes at least %d argument%s (%s given)"
                        % (len(argtypes), plural, len(args)))
                else:
                    # For cdecl functions, we allow more actual arguments
                    # than the length of the argtypes tuple.
                    args = args[:len(self._argtypes_)]
            else:
                plural = len(self._argtypes_) > 1 and "s" or ""
                raise TypeError(
                    "This function takes %d argument%s (%s given)"
                    % (len(self._argtypes_), plural, len(args)))

            try:
                newargs = self._convert_args_for_callback(argtypes, args)
            except (UnicodeError, TypeError, ValueError), e:
                raise ArgumentError(str(e))
            try:
                res = self.callable(*newargs)
            except:
                exc_info = sys.exc_info()
                traceback.print_tb(exc_info[2], file=sys.stderr)
                print >>sys.stderr, "%s: %s" % (exc_info[0].__name__, exc_info[1])
                return 0
            if self._restype_ is not None:
                return res
            return

        if argtypes is None:
            warnings.warn('C function without declared arguments called',
                          RuntimeWarning, stacklevel=2)
            argtypes = []

        if self._com_index:
            from ctypes import cast, c_void_p, POINTER
            if not args:
                raise ValueError(
                    "native COM method call without 'this' parameter"
                    )
            thisarg = cast(args[0], POINTER(POINTER(c_void_p)))
            keepalives, newargs, argtypes, outargs = self._convert_args(argtypes,
                                                                        args[1:], kwargs)
            newargs.insert(0, args[0].value)
            argtypes.insert(0, c_void_p)
        else:
            thisarg = None
            keepalives, newargs, argtypes, outargs = self._convert_args(argtypes,
                                                                        args, kwargs)

        funcptr = self._getfuncptr(argtypes, self._restype_, thisarg)
        result = self._call_funcptr(funcptr, *newargs)
        result = self._do_errcheck(result, args)

        if not outargs:
            return result

        simple_cdata = type(c_void_p()).__bases__[0]
        outargs = [x.value if type(x).__bases__[0] is simple_cdata else x
                   for x in outargs]

        if len(outargs) == 1:
            return outargs[0]
        return tuple(outargs)

    def _call_funcptr(self, funcptr, *newargs):

        if self._flags_ & _rawffi.FUNCFLAG_USE_ERRNO:
            tmp = _rawffi.get_errno()
            _rawffi.set_errno(get_errno())
            set_errno(tmp)
        if self._flags_ & _rawffi.FUNCFLAG_USE_LASTERROR:
            tmp = _rawffi.get_last_error()
            _rawffi.set_last_error(get_last_error())
            set_last_error(tmp)
        try:
            result = funcptr(*newargs)
        finally:
            if self._flags_ & _rawffi.FUNCFLAG_USE_ERRNO:
                tmp = _rawffi.get_errno()
                _rawffi.set_errno(get_errno())
                set_errno(tmp)
            if self._flags_ & _rawffi.FUNCFLAG_USE_LASTERROR:
                tmp = _rawffi.get_last_error()
                _rawffi.set_last_error(get_last_error())
                set_last_error(tmp)
        #
        try:
            return self._build_result(self._restype_, result, newargs)
        finally:
            funcptr.free_temp_buffers()

    def _do_errcheck(self, result, args):
        # The 'errcheck' protocol
        if self._errcheck_:
            v = self._errcheck_(result, self, args)
            # If the errcheck funtion failed, let it throw
            # If the errcheck function returned newargs unchanged,
            # continue normal processing.
            # If the errcheck function returned something else,
            # use that as result.
            if v is not args:
                return v
        return result

    def _getfuncptr_fromaddress(self, argtypes, restype):
        address = self._get_address()
        ffiargs = [argtype.get_ffi_argtype() for argtype in argtypes]
        ffires = restype.get_ffi_argtype()
        return _ffi.FuncPtr.fromaddr(address, '', ffiargs, ffires, self._flags_)

    def _getfuncptr(self, argtypes, restype, thisarg=None):
        if self._ptr is not None and (argtypes is self._argtypes_ or argtypes == self._argtypes_):
            return self._ptr
        if restype is None or not isinstance(restype, _CDataMeta):
            import ctypes
            restype = ctypes.c_int
        if self._buffer is not None:
            ptr = self._getfuncptr_fromaddress(argtypes, restype)
            if argtypes == self._argtypes_:
                self._ptr = ptr
            return ptr

        if self._com_index:
            # extract the address from the object's virtual table
            if not thisarg:
                raise ValueError("COM method call without VTable")
            ptr = thisarg[0][self._com_index - 0x1000]
            ffiargs = [argtype.get_ffi_argtype() for argtype in argtypes]
            ffires = restype.get_ffi_argtype()
            return _ffi.FuncPtr.fromaddr(ptr, '', ffiargs, ffires, self._flags_)
        
        cdll = self.dll._handle
        try:
            ffi_argtypes = [argtype.get_ffi_argtype() for argtype in argtypes]
            ffi_restype = restype.get_ffi_argtype()
            self._ptr = cdll.getfunc(self.name, ffi_argtypes, ffi_restype)
            return self._ptr
        except AttributeError:
            if self._flags_ & _rawffi.FUNCFLAG_CDECL:
                raise

            # Win64 has no stdcall calling conv, so it should also not have the
            # name mangling of it.
            if WIN64:
                raise
            # For stdcall, try mangled names:
            # funcname -> _funcname@<n>
            # where n is 0, 4, 8, 12, ..., 128
            for i in range(33):
                mangled_name = "_%s@%d" % (self.name, i*4)
                try:
                    return cdll.getfunc(mangled_name,
                                        ffi_argtypes, ffi_restype,
                                        # XXX self._flags_
                                        )
                except AttributeError:
                    pass
            raise

    @classmethod
    def _conv_param(cls, argtype, arg):
        if argtype is not None:
            arg = argtype.from_param(arg)
        if hasattr(arg, '_as_parameter_'):
            arg = arg._as_parameter_
        if isinstance(arg, _CData):
            return arg, arg._to_ffi_param(), type(arg)
        #
        # non-usual case: we do the import here to save a lot of code in the
        # jit trace of the normal case
        from ctypes import c_char_p, c_wchar_p, c_void_p, c_int
        #
        if isinstance(arg, str):
            cobj = c_char_p(arg)
        elif isinstance(arg, unicode):
            cobj = c_wchar_p(arg)
        elif arg is None:
            cobj = c_void_p()
        elif isinstance(arg, (int, long)):
            cobj = c_int(arg)
        else:
            raise TypeError("Don't know how to handle %s" % (arg,))

        return cobj, cobj._to_ffi_param(), type(cobj)

    def _convert_args_for_callback(self, argtypes, args):
        assert len(argtypes) == len(args)
        newargs = []
        for argtype, arg in zip(argtypes, args):
            param = argtype.from_param(arg)
            _type_ = getattr(argtype, '_type_', None)
            if _type_ == 'P': # special-case for c_void_p
                param = param._get_buffer_value()
            elif self._is_primitive(argtype):
                param = param.value
            newargs.append(param)
        return newargs

    def _convert_args(self, argtypes, args, kwargs, marker=object()):
        newargs = []
        outargs = []
        keepalives = []
        newargtypes = []
        total = len(args)
        paramflags = self._paramflags
        inargs_idx = 0

        if not paramflags and total < len(argtypes):
            raise TypeError("not enough arguments")

        for i, argtype in enumerate(argtypes):
            flag = 0
            name = None
            defval = marker
            if paramflags:
                paramflag = paramflags[i]
                paramlen = len(paramflag)
                name = None
                if paramlen == 1:
                    flag = paramflag[0]
                elif paramlen == 2:
                    flag, name = paramflag
                elif paramlen == 3:
                    flag, name, defval = paramflag
                flag = flag & PARAMFLAG_COMBINED
                if flag == PARAMFLAG_FIN | PARAMFLAG_FLCID:
                    val = defval
                    if val is marker:
                        val = 0
                    keepalive, newarg, newargtype = self._conv_param(argtype, val)
                    keepalives.append(keepalive)
                    newargs.append(newarg)
                    newargtypes.append(newargtype)
                elif flag in (0, PARAMFLAG_FIN):
                    if inargs_idx < total:
                        val = args[inargs_idx]
                        inargs_idx += 1
                    elif kwargs and name in kwargs:
                        val = kwargs[name]
                        inargs_idx += 1
                    elif defval is not marker:
                        val = defval
                    elif name:
                        raise TypeError("required argument '%s' missing" % name)
                    else:
                        raise TypeError("not enough arguments")
                    keepalive, newarg, newargtype = self._conv_param(argtype, val)
                    keepalives.append(keepalive)
                    newargs.append(newarg)
                    newargtypes.append(newargtype)
                elif flag == PARAMFLAG_FOUT:
                    if defval is not marker:
                        outargs.append(defval)
                        keepalive, newarg, newargtype = self._conv_param(argtype, defval)
                    else:
                        import ctypes
                        val = argtype._type_()
                        outargs.append(val)
                        keepalive = None
                        newarg = ctypes.byref(val)
                        newargtype = type(newarg)
                    keepalives.append(keepalive)
                    newargs.append(newarg)
                    newargtypes.append(newargtype)
                else:
                    raise ValueError("paramflag %d not yet implemented" % flag)
            else:
                try:
                    keepalive, newarg, newargtype = self._conv_param(argtype, args[i])
                except (UnicodeError, TypeError, ValueError), e:
                    raise ArgumentError(str(e))
                keepalives.append(keepalive)
                newargs.append(newarg)
                newargtypes.append(newargtype)
                inargs_idx += 1

        if len(newargs) < len(args):
            extra = args[len(newargs):]
            for i, arg in enumerate(extra):
                try:
                    keepalive, newarg, newargtype = self._conv_param(None, arg)
                except (UnicodeError, TypeError, ValueError), e:
                    raise ArgumentError(str(e))
                keepalives.append(keepalive)
                newargs.append(newarg)
                newargtypes.append(newargtype)
        return keepalives, newargs, newargtypes, outargs

    @staticmethod
    def _is_primitive(argtype):
        return argtype.__bases__[0] is _SimpleCData

    def _wrap_result(self, restype, result):
        """
        Convert from low-level repr of the result to the high-level python
        one.
        """
        # hack for performance: if restype is a "simple" primitive type, don't
        # allocate the buffer because it's going to be thrown away immediately
        if self._is_primitive(restype) and not restype._is_pointer_like():
            return result
        #
        shape = restype._ffishape
        if is_struct_shape(shape):
            buf = result
        else:
            buf = _rawffi.Array(shape)(1, autofree=True)
            buf[0] = result
        retval = restype._CData_retval(buf)
        return retval

    def _build_result(self, restype, result, argsandobjs):
        """Build the function result:
           If there is no OUT parameter, return the actual function result
           If there is one OUT parameter, return it
           If there are many OUT parameters, return a tuple"""

        # XXX: note for the future: the function used to take a "resbuffer",
        # i.e. an array of ints. Now it takes a result, which is already a
        # python object. All places that do "resbuffer[0]" should check that
        # result is actually an int and just use it.
        #
        # Also, argsandobjs used to be "args" in __call__, now it's "newargs"
        # (i.e., the already unwrapped objects). It's used only when we have a
        # PARAMFLAG_FOUT and it's probably wrong, I'll fix it when I find a
        # failing test

        retval = None

        if restype is not None:
            checker = getattr(self.restype, '_check_retval_', None)
            if checker:
                val = restype(result)
                # the original ctypes seems to make the distinction between
                # classes defining a new type, and their subclasses
                if '_type_' in restype.__dict__:
                    val = val.value
                # XXX Raise a COMError when restype is HRESULT and
                # checker(val) fails.  How to check for restype == HRESULT?
                if self._com_index:
                    if result & 0x80000000:
                        raise get_com_error(result, None, None)
                else:
                    retval = checker(val)
            elif not isinstance(restype, _CDataMeta):
                retval = restype(result)
            else:
                retval = self._wrap_result(restype, result)

        return retval

    def __nonzero__(self):
        return self._com_index is not None or bool(self._buffer[0])

    def __del__(self):
        if self._needs_free:
            # XXX we need to find a bad guy here
            if self._buffer is None:
                return
            self._buffer.free()
            self._buffer = None
            if isinstance(self._ptr, _rawffi.CallbackPtr):
                self._ptr.free()
                self._ptr = None
            self._needs_free = False


def make_fastpath_subclass(CFuncPtr):
    if CFuncPtr._is_fastpath:
        return CFuncPtr
    #
    try:
        return make_fastpath_subclass.memo[CFuncPtr]
    except KeyError:
        pass

    class CFuncPtrFast(CFuncPtr):

        _is_fastpath = True
        _slowpath_allowed = True # set to False by tests

        @classmethod
        def enable_fastpath_maybe(cls, obj):
            if (obj.callable is None and
                obj._com_index is None):
                obj.__class__ = cls

        def __rollback(self):
            assert self._slowpath_allowed
            self.__class__ = CFuncPtr

        # disable the fast path if we reset argtypes
        def _setargtypes(self, argtypes):
            self.__rollback()
            self._setargtypes(argtypes)
        argtypes = property(CFuncPtr._getargtypes, _setargtypes)

        def _setcallable(self, func):
            self.__rollback()
            self.callable = func
        callable = property(lambda x: None, _setcallable)

        def _setcom_index(self, idx):
            self.__rollback()
            self._com_index = idx
        _com_index = property(lambda x: None, _setcom_index)

        def __call__(self, *args):
            thisarg = None
            argtypes = self._argtypes_
            restype = self._restype_
            funcptr = self._getfuncptr(argtypes, restype, thisarg)
            try:
                result = self._call_funcptr(funcptr, *args)
                result = self._do_errcheck(result, args)
            except (TypeError, ArgumentError, UnicodeDecodeError):
                assert self._slowpath_allowed
                return CFuncPtr.__call__(self, *args)
            return result

    make_fastpath_subclass.memo[CFuncPtr] = CFuncPtrFast
    return CFuncPtrFast
make_fastpath_subclass.memo = {}
