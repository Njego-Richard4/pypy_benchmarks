
""" Tests for register allocation for common constructs
"""

import re
from rpython.jit.metainterp.history import TargetToken, BasicFinalDescr,\
     JitCellToken, BasicFailDescr, AbstractDescr
from rpython.jit.backend.llsupport.gc import GcLLDescription, GcLLDescr_boehm,\
     GcLLDescr_framework, GcCache, JitFrameDescrs
from rpython.jit.backend.detect_cpu import getcpuclass
from rpython.jit.backend.llsupport.symbolic import WORD
from rpython.jit.backend.llsupport import jitframe
from rpython.rtyper.lltypesystem import lltype, llmemory, rffi
from rpython.rtyper.annlowlevel import llhelper, llhelper_args

from rpython.jit.backend.llsupport.test.test_regalloc_integration import BaseTestRegalloc
from rpython.jit.codewriter.effectinfo import EffectInfo
from rpython.jit.codewriter import longlong
from rpython.rlib.objectmodel import invoke_around_extcall

CPU = getcpuclass()

def getmap(frame):
    r = ''
    for elem in frame.jf_gcmap:
        elem = bin(elem)[2:]
        elem = '0' * (WORD * 8 - len(elem)) + elem
        r = elem + r
    return r[r.find('1'):]

class TestRegallocGcIntegration(BaseTestRegalloc):
    
    cpu = CPU(None, None)
    cpu.gc_ll_descr = GcLLDescr_boehm(None, None, None)
    cpu.setup_once()
    
    S = lltype.GcForwardReference()
    S.become(lltype.GcStruct('S', ('field', lltype.Ptr(S)),
                             ('int', lltype.Signed)))

    fielddescr = cpu.fielddescrof(S, 'field')

    struct_ptr = lltype.malloc(S)
    struct_ref = lltype.cast_opaque_ptr(llmemory.GCREF, struct_ptr)
    child_ptr = lltype.nullptr(S)
    struct_ptr.field = child_ptr


    intdescr = cpu.fielddescrof(S, 'int')
    ptr0 = struct_ref

    targettoken = TargetToken()
    targettoken2 = TargetToken()

    namespace = locals().copy()

    def test_basic(self):
        ops = '''
        [p0]
        p1 = getfield_gc(p0, descr=fielddescr)
        finish(p1)
        '''
        self.interpret(ops, [self.struct_ptr])
        assert not self.getptr(0, lltype.Ptr(self.S))

    def test_guard(self):
        ops = '''
        [i0, p0, i1, p1]
        p3 = getfield_gc(p0, descr=fielddescr)
        guard_true(i0) [p0, i1, p1, p3]
        '''
        s1 = lltype.malloc(self.S)
        s2 = lltype.malloc(self.S)
        s1.field = s2
        self.interpret(ops, [0, s1, 1, s2])
        frame = lltype.cast_opaque_ptr(jitframe.JITFRAMEPTR, self.deadframe)
        # p0 and p3 should be in registers, p1 not so much
        assert self.getptr(0, lltype.Ptr(self.S)) == s1
        # the gcmap should contain three things, p0, p1 and p3
        # p3 stays in a register
        # while p0 and p1 are on the frame
        b = getmap(frame)
        nos = [len(b) - 1 - i.start() for i in re.finditer('1', b)]
        nos.reverse()
        if self.cpu.backend_name.startswith('x86'):
            if self.cpu.IS_64_BIT:
                assert nos == [11, 12, 31]
            else:
                assert nos ==  [4, 5, 25]
        elif self.cpu.backend_name.startswith('arm'):
            assert nos == [9, 10, 47]
        else:
            raise Exception("write the data here")
        assert frame.jf_frame[nos[0]]
        assert frame.jf_frame[nos[1]]
        assert frame.jf_frame[nos[2]]

    def test_rewrite_constptr(self):
        ops = '''
        []
        p1 = getfield_gc(ConstPtr(struct_ref), descr=fielddescr)
        finish(p1)
        '''
        self.interpret(ops, [])
        assert not self.getptr(0, lltype.Ptr(self.S))

    def test_bug_0(self):
        ops = '''
        [i0, i1, i2, i3, i4, i5, i6, i7, i8]
        label(i0, i1, i2, i3, i4, i5, i6, i7, i8, descr=targettoken)
        guard_value(i2, 1) [i2, i3, i4, i5, i6, i7, i0, i1, i8]
        guard_class(i4, 138998336) [i4, i5, i6, i7, i0, i1, i8]
        i11 = getfield_gc(i4, descr=intdescr)
        guard_nonnull(i11) [i4, i5, i6, i7, i0, i1, i11, i8]
        i13 = getfield_gc(i11, descr=intdescr)
        guard_isnull(i13) [i4, i5, i6, i7, i0, i1, i11, i8]
        i15 = getfield_gc(i4, descr=intdescr)
        i17 = int_lt(i15, 0)
        guard_false(i17) [i4, i5, i6, i7, i0, i1, i11, i15, i8]
        i18 = getfield_gc(i11, descr=intdescr)
        i19 = int_ge(i15, i18)
        guard_false(i19) [i4, i5, i6, i7, i0, i1, i11, i15, i8]
        i20 = int_lt(i15, 0)
        guard_false(i20) [i4, i5, i6, i7, i0, i1, i11, i15, i8]
        i21 = getfield_gc(i11, descr=intdescr)
        i22 = getfield_gc(i11, descr=intdescr)
        i23 = int_mul(i15, i22)
        i24 = int_add(i21, i23)
        i25 = getfield_gc(i4, descr=intdescr)
        i27 = int_add(i25, 1)
        setfield_gc(i4, i27, descr=intdescr)
        i29 = getfield_raw(144839744, descr=intdescr)
        i31 = int_and(i29, -2141192192)
        i32 = int_is_true(i31)
        guard_false(i32) [i4, i6, i7, i0, i1, i24]
        i33 = getfield_gc(i0, descr=intdescr)
        guard_value(i33, ConstPtr(ptr0)) [i4, i6, i7, i0, i1, i33, i24]
        jump(i0, i1, 1, 17, i4, ConstPtr(ptr0), i6, i7, i24, descr=targettoken)
        '''
        self.interpret(ops, [0, 0, 0, 0, 0, 0, 0, 0, 0], run=False)

NOT_INITIALIZED = chr(0xdd)

class GCDescrFastpathMalloc(GcLLDescription):
    gcrootmap = None
    passes_frame = True
    write_barrier_descr = None

    def __init__(self, callback):
        GcLLDescription.__init__(self, None)
        # create a nursery
        NTP = rffi.CArray(lltype.Char)
        self.nursery = lltype.malloc(NTP, 64, flavor='raw')
        for i in range(64):
            self.nursery[i] = NOT_INITIALIZED
        self.addrs = lltype.malloc(rffi.CArray(lltype.Signed), 2,
                                   flavor='raw')
        self.addrs[0] = rffi.cast(lltype.Signed, self.nursery)
        self.addrs[1] = self.addrs[0] + 64
        self.calls = []
        def malloc_slowpath(size, frame):
            if callback is not None:
                callback(frame)
            if self.gcrootmap is not None:   # hook
                self.gcrootmap.hook_malloc_slowpath()
            self.calls.append(size)
            # reset the nursery
            nadr = rffi.cast(lltype.Signed, self.nursery)
            self.addrs[0] = nadr + size
            return nadr
        self.generate_function('malloc_nursery', malloc_slowpath,
                               [lltype.Signed, jitframe.JITFRAMEPTR],
                               lltype.Signed)

    def get_nursery_free_addr(self):
        return rffi.cast(lltype.Signed, self.addrs)

    def get_nursery_top_addr(self):
        return rffi.cast(lltype.Signed, self.addrs) + WORD

    def get_malloc_slowpath_addr(self):
        return self.get_malloc_fn_addr('malloc_nursery')

    def check_nothing_in_nursery(self):
        # CALL_MALLOC_NURSERY should not write anything in the nursery
        for i in range(64):
            assert self.nursery[i] == NOT_INITIALIZED

class TestMallocFastpath(BaseTestRegalloc):

    def teardown_method(self, method):
        lltype.free(self.cpu.gc_ll_descr.addrs, flavor='raw')
        lltype.free(self.cpu.gc_ll_descr.nursery, flavor='raw')

    def getcpu(self, callback):
        cpu = CPU(None, None)
        cpu.gc_ll_descr = GCDescrFastpathMalloc(callback)
        cpu.setup_once()
        return cpu

    def test_malloc_fastpath(self):
        self.cpu = self.getcpu(None)
        ops = '''
        [i0]
        p0 = call_malloc_nursery(16)
        p1 = call_malloc_nursery(32)
        p2 = call_malloc_nursery(16)
        guard_true(i0) [p0, p1, p2]
        '''
        self.interpret(ops, [0])
        # check the returned pointers
        gc_ll_descr = self.cpu.gc_ll_descr
        nurs_adr = rffi.cast(lltype.Signed, gc_ll_descr.nursery)
        ref = lambda n: self.cpu.get_ref_value(self.deadframe, n)
        assert rffi.cast(lltype.Signed, ref(0)) == nurs_adr + 0
        assert rffi.cast(lltype.Signed, ref(1)) == nurs_adr + 16
        assert rffi.cast(lltype.Signed, ref(2)) == nurs_adr + 48
        # check the nursery content and state
        gc_ll_descr.check_nothing_in_nursery()
        assert gc_ll_descr.addrs[0] == nurs_adr + 64
        # slowpath never called
        assert gc_ll_descr.calls == []

    def test_malloc_nursery_varsize_small(self):
        self.cpu = self.getcpu(None)
        ops = '''
        [i0, i1, i2]
        p0 = call_malloc_nursery_varsize_small(i0)
        p1 = call_malloc_nursery_varsize_small(i1)
        p2 = call_malloc_nursery_varsize_small(i2)
        guard_true(i0) [p0, p1, p2]
        ''' 
        self.interpret(ops, [16, 32, 16])
        # check the returned pointers
        gc_ll_descr = self.cpu.gc_ll_descr
        nurs_adr = rffi.cast(lltype.Signed, gc_ll_descr.nursery)
        ref = lambda n: self.cpu.get_ref_value(self.deadframe, n)
        assert rffi.cast(lltype.Signed, ref(0)) == nurs_adr + 0
        assert rffi.cast(lltype.Signed, ref(1)) == nurs_adr + 16
        assert rffi.cast(lltype.Signed, ref(2)) == nurs_adr + 48
        # check the nursery content and state
        gc_ll_descr.check_nothing_in_nursery()
        assert gc_ll_descr.addrs[0] == nurs_adr + 64
        # slowpath never called
        assert gc_ll_descr.calls == []

    def test_malloc_slowpath(self):
        def check(frame):
            expected_size = 1
            idx = 0
            if self.cpu.backend_name.startswith('arm'):
                # jitframe fixed part is larger here
                expected_size = 2
                idx = 1
            assert len(frame.jf_gcmap) == expected_size
            if self.cpu.IS_64_BIT:
                assert frame.jf_gcmap[idx] == (1<<29) | (1 << 30)
            else:
                assert frame.jf_gcmap[idx] == (1<<24) | (1 << 23)

        self.cpu = self.getcpu(check)
        ops = '''
        [i0]
        p0 = call_malloc_nursery(16)
        p1 = call_malloc_nursery(32)
        p2 = call_malloc_nursery(24)     # overflow
        guard_true(i0) [p0, p1, p2]
        '''
        self.interpret(ops, [0])
        # check the returned pointers
        gc_ll_descr = self.cpu.gc_ll_descr
        nurs_adr = rffi.cast(lltype.Signed, gc_ll_descr.nursery)
        ref = lambda n: self.cpu.get_ref_value(self.deadframe, n)
        assert rffi.cast(lltype.Signed, ref(0)) == nurs_adr + 0
        assert rffi.cast(lltype.Signed, ref(1)) == nurs_adr + 16
        assert rffi.cast(lltype.Signed, ref(2)) == nurs_adr + 0
        # check the nursery content and state
        gc_ll_descr.check_nothing_in_nursery()
        assert gc_ll_descr.addrs[0] == nurs_adr + 24
        # this should call slow path once
        assert gc_ll_descr.calls == [24]

    def test_save_regs_around_malloc(self):
        def check(frame):
            x = frame.jf_gcmap
            if self.cpu.IS_64_BIT:
                assert len(x) == 1
                assert (bin(x[0]).count('1') ==
                        '0b1111100000000000000001111111011110'.count('1'))
            else:
                assert len(x) == 2
                s = bin(x[0]).count('1') + bin(x[1]).count('1')
                assert s == 16
            # all but two registers + some stuff on stack
        
        self.cpu = self.getcpu(check)
        S1 = lltype.GcStruct('S1')
        S2 = lltype.GcStruct('S2', ('s0', lltype.Ptr(S1)),
                                   ('s1', lltype.Ptr(S1)),
                                   ('s2', lltype.Ptr(S1)),
                                   ('s3', lltype.Ptr(S1)),
                                   ('s4', lltype.Ptr(S1)),
                                   ('s5', lltype.Ptr(S1)),
                                   ('s6', lltype.Ptr(S1)),
                                   ('s7', lltype.Ptr(S1)),
                                   ('s8', lltype.Ptr(S1)),
                                   ('s9', lltype.Ptr(S1)),
                                   ('s10', lltype.Ptr(S1)),
                                   ('s11', lltype.Ptr(S1)),
                                   ('s12', lltype.Ptr(S1)),
                                   ('s13', lltype.Ptr(S1)),
                                   ('s14', lltype.Ptr(S1)),
                                   ('s15', lltype.Ptr(S1)))
        cpu = self.cpu
        self.namespace = self.namespace.copy()
        for i in range(16):
            self.namespace['ds%i' % i] = cpu.fielddescrof(S2, 's%d' % i)
        ops = '''
        [i0, p0]
        p1 = getfield_gc(p0, descr=ds0)
        p2 = getfield_gc(p0, descr=ds1)
        p3 = getfield_gc(p0, descr=ds2)
        p4 = getfield_gc(p0, descr=ds3)
        p5 = getfield_gc(p0, descr=ds4)
        p6 = getfield_gc(p0, descr=ds5)
        p7 = getfield_gc(p0, descr=ds6)
        p8 = getfield_gc(p0, descr=ds7)
        p9 = getfield_gc(p0, descr=ds8)
        p10 = getfield_gc(p0, descr=ds9)
        p11 = getfield_gc(p0, descr=ds10)
        p12 = getfield_gc(p0, descr=ds11)
        p13 = getfield_gc(p0, descr=ds12)
        p14 = getfield_gc(p0, descr=ds13)
        p15 = getfield_gc(p0, descr=ds14)
        p16 = getfield_gc(p0, descr=ds15)
        #
        # now all registers are in use
        p17 = call_malloc_nursery(40)
        p18 = call_malloc_nursery(40)     # overflow
        #
        guard_true(i0) [p1, p2, p3, p4, p5, p6, \
            p7, p8, p9, p10, p11, p12, p13, p14, p15, p16]
        '''
        s2 = lltype.malloc(S2)
        for i in range(16):
            setattr(s2, 's%d' % i, lltype.malloc(S1))
        s2ref = lltype.cast_opaque_ptr(llmemory.GCREF, s2)
        #
        self.interpret(ops, [0, s2ref])
        gc_ll_descr = cpu.gc_ll_descr
        gc_ll_descr.check_nothing_in_nursery()
        assert gc_ll_descr.calls == [40]
        # check the returned pointers
        for i in range(16):
            s1ref = self.cpu.get_ref_value(self.deadframe, i)
            s1 = lltype.cast_opaque_ptr(lltype.Ptr(S1), s1ref)
            assert s1 == getattr(s2, 's%d' % i)

class MockShadowStackRootMap(object):
    is_shadow_stack = True
    
    def __init__(self):
        TP = rffi.CArray(lltype.Signed)
        self.stack = lltype.malloc(TP, 10, flavor='raw')
        self.stack_addr = lltype.malloc(TP, 1,
                                        flavor='raw')
        self.stack_addr[0] = rffi.cast(lltype.Signed, self.stack)

    def __del__(self):
        lltype.free(self.stack_addr, flavor='raw')        
        lltype.free(self.stack, flavor='raw')

    def register_asm_addr(self, start, mark):
        pass

    def get_root_stack_top_addr(self):
        return rffi.cast(lltype.Signed, self.stack_addr)

class WriteBarrierDescr(AbstractDescr):
    jit_wb_cards_set = 0
    jit_wb_if_flag_singlebyte = 1
    
    def __init__(self, gc_ll_descr):
        def write_barrier(frame):
            gc_ll_descr.write_barrier_on_frame_called = frame

        self.write_barrier_fn = llhelper_args(write_barrier,
                                              [lltype.Signed], lltype.Void)

    def get_write_barrier_fn(self, cpu):
        return self.write_barrier_fn

# a copy of JITFRAM that has 'hdr' field for tests

def jitframe_allocate(frame_info):
    frame = lltype.malloc(JITFRAME, frame_info.jfi_frame_depth, zero=True)
    frame.jf_frame_info = frame_info
    return frame

JITFRAME = lltype.GcStruct(
    'JITFRAME',
    ('hdr', lltype.Signed),
    ('jf_frame_info', lltype.Ptr(jitframe.JITFRAMEINFO)),
    ('jf_descr', llmemory.GCREF),
    ('jf_force_descr', llmemory.GCREF),
    ('jf_extra_stack_depth', lltype.Signed),
    ('jf_guard_exc', llmemory.GCREF),
    ('jf_gcmap', lltype.Ptr(jitframe.GCMAP)),
    ('jf_gc_trace_state', lltype.Signed),
    ('jf_frame', lltype.Array(lltype.Signed)),
    adtmeths = {
        'allocate': jitframe_allocate,
    },
)

JITFRAMEPTR = lltype.Ptr(JITFRAME)

class GCDescrShadowstackDirect(GcLLDescr_framework):
    layoutbuilder = None

    class GCClass:
        JIT_WB_IF_FLAG = 0

    def __init__(self):
        GcCache.__init__(self, False, None)
        self._generated_functions = []
        self.gcrootmap = MockShadowStackRootMap()
        self.write_barrier_descr = WriteBarrierDescr(self)
        self.nursery_ptrs = lltype.malloc(rffi.CArray(lltype.Signed), 2,
                                          flavor='raw')
        self._initialize_for_tests()
        self.frames = []

        def malloc_slowpath(size):
            self._collect()
            res = self.nursery_ptrs[0]
            self.nursery_ptrs[0] += size
            return res

        self.malloc_slowpath_fnptr = llhelper_args(malloc_slowpath,
                                                   [lltype.Signed],
                                                   lltype.Signed)
        self.all_nurseries = []

    def init_nursery(self, nursery_size=None):
        if nursery_size is None:
            nursery_size = self.nursery_size
        else:
            self.nursery_size = nursery_size
        self.nursery = lltype.malloc(rffi.CArray(lltype.Char), nursery_size,
                                     flavor='raw', zero=True,
                                     track_allocation=False)
        self.nursery_ptrs[0] = rffi.cast(lltype.Signed, self.nursery)
        self.nursery_ptrs[1] = self.nursery_ptrs[0] + nursery_size
        self.nursery_addr = rffi.cast(lltype.Signed, self.nursery_ptrs)
        self.all_nurseries.append(self.nursery)
        if hasattr(self, 'collections'):
            self.collections.reverse()

    def _collect(self):
        gcmap = unpack_gcmap(self.frames[-1])
        col = self.collections.pop()
        frame = self.frames[-1].jf_frame
        start = rffi.cast(lltype.Signed, self.nursery)
        assert len(gcmap) == len(col)
        pos = [frame[item] for item in gcmap]
        pos.sort()
        for i in range(len(gcmap)):
            assert col[i] + start == pos[i]
        self.frames[-1].hdr |= 1
        self.init_nursery()

    def malloc_jitframe(self, frame_info):
        """ Allocate a new frame, overwritten by tests
        """
        frame = JITFRAME.allocate(frame_info)
        self.frames.append(frame)
        return frame

    def getframedescrs(self, cpu):
        descrs = JitFrameDescrs()
        descrs.arraydescr = cpu.arraydescrof(JITFRAME)
        for name in ['jf_descr', 'jf_guard_exc', 'jf_force_descr',
                     'jf_frame_info', 'jf_gcmap', 'jf_extra_stack_depth']:
            setattr(descrs, name, cpu.fielddescrof(JITFRAME, name))
        descrs.jfi_frame_depth = cpu.fielddescrof(jitframe.JITFRAMEINFO,
                                                  'jfi_frame_depth')
        descrs.jfi_frame_size = cpu.fielddescrof(jitframe.JITFRAMEINFO,
                                                  'jfi_frame_size')
        return descrs

    def do_write_barrier(self, gcref_struct, gcref_newptr):
        pass

    def get_malloc_slowpath_addr(self):
        return self.malloc_slowpath_fnptr

    def get_nursery_free_addr(self):
        return self.nursery_addr

    def get_nursery_top_addr(self):
        return self.nursery_addr + rffi.sizeof(lltype.Signed)

    def __del__(self):
        for nursery in self.all_nurseries:
            lltype.free(nursery, flavor='raw', track_allocation=False)
        lltype.free(self.nursery_ptrs, flavor='raw')
    
def unpack_gcmap(frame):
    res = []
    val = 0
    for i in range(len(frame.jf_gcmap)):
        item = frame.jf_gcmap[i]
        if item == 0:
            val += WORD * 8
        while item != 0:
            if item & 1:
                res.append(val)
            val += 1
            item >>= 1
    return res

class TestGcShadowstackDirect(BaseTestRegalloc):

    def setup_method(self, meth):
        cpu = CPU(None, None)
        cpu.gc_ll_descr = GCDescrShadowstackDirect()
        wbd = cpu.gc_ll_descr.write_barrier_descr
        wbd.jit_wb_if_flag_byteofs = 0 # directly into 'hdr' field
        S = lltype.GcForwardReference()
        S.become(lltype.GcStruct('S',
                                 ('hdr', lltype.Signed),
                                 ('x', lltype.Ptr(S))))
        cpu.gc_ll_descr.fielddescr_tid = cpu.fielddescrof(S, 'hdr')
        self.S = S
        self.cpu = cpu

    def test_shadowstack_call(self):
        cpu = self.cpu
        cpu.gc_ll_descr.init_nursery(100)
        cpu.setup_once() 
        S = self.S
        frames = []
        
        def check(i):
            assert cpu.gc_ll_descr.gcrootmap.stack[0] == i
            frame = rffi.cast(JITFRAMEPTR, i)
            assert len(frame.jf_frame) == self.cpu.JITFRAME_FIXED_SIZE + 4
            # we "collect"
            frames.append(frame)
            new_frame = JITFRAME.allocate(frame.jf_frame_info)
            gcmap = unpack_gcmap(frame)
            if self.cpu.IS_64_BIT:
                assert gcmap == [28, 29, 30]
            elif self.cpu.backend_name.startswith('arm'):
                assert gcmap == [44, 45, 46]
                pass
            else:
                assert gcmap == [22, 23, 24]
            for item, s in zip(gcmap, new_items):
                new_frame.jf_frame[item] = rffi.cast(lltype.Signed, s)
            assert cpu.gc_ll_descr.gcrootmap.stack[0] == rffi.cast(lltype.Signed, frame)
            cpu.gc_ll_descr.gcrootmap.stack[0] = rffi.cast(lltype.Signed, new_frame)
            frames.append(new_frame)

        def check2(i):
            assert cpu.gc_ll_descr.gcrootmap.stack[0] == i
            frame = rffi.cast(JITFRAMEPTR, i)
            assert frame == frames[1]
            assert frame != frames[0]

        CHECK = lltype.FuncType([lltype.Signed], lltype.Void)
        checkptr = llhelper(lltype.Ptr(CHECK), check)
        check2ptr = llhelper(lltype.Ptr(CHECK), check2)
        checkdescr = cpu.calldescrof(CHECK, CHECK.ARGS, CHECK.RESULT,
                                          EffectInfo.MOST_GENERAL)

        loop = self.parse("""
        [p0, p1, p2]
        pf = force_token() # this is the frame
        call(ConstClass(check_adr), pf, descr=checkdescr) # this can collect
        p3 = getfield_gc(p0, descr=fielddescr)
        pf2 = force_token()
        call(ConstClass(check2_adr), pf2, descr=checkdescr)
        guard_nonnull(p3, descr=faildescr) [p0, p1, p2, p3]
        p4 = getfield_gc(p0, descr=fielddescr)
        finish(p4, descr=finaldescr)
        """, namespace={'finaldescr': BasicFinalDescr(),
                        'faildescr': BasicFailDescr(),
                        'check_adr': checkptr, 'check2_adr': check2ptr,
                        'checkdescr': checkdescr,
                        'fielddescr': cpu.fielddescrof(S, 'x')})
        token = JitCellToken()
        cpu.compile_loop(loop.inputargs, loop.operations, token)
        p0 = lltype.malloc(S, zero=True)
        p1 = lltype.malloc(S)
        p2 = lltype.malloc(S)
        new_items = [lltype.malloc(S), lltype.malloc(S), lltype.malloc(S)]
        new_items[0].x = new_items[2]
        frame = cpu.execute_token(token, p0, p1, p2)
        frame = lltype.cast_opaque_ptr(JITFRAMEPTR, frame)
        gcmap = unpack_gcmap(lltype.cast_opaque_ptr(JITFRAMEPTR, frame))
        assert len(gcmap) == 1
        assert gcmap[0] < self.cpu.JITFRAME_FIXED_SIZE
        item = rffi.cast(lltype.Ptr(S), frame.jf_frame[gcmap[0]])
        assert item == new_items[2]

    def test_shadowstack_collecting_call_float(self):
        cpu = self.cpu

        def float_return(i, f):
            # mark frame for write barrier
            frame = rffi.cast(lltype.Ptr(JITFRAME), i)
            frame.hdr |= 1
            return 1.2 + f

        FUNC = lltype.FuncType([lltype.Signed, lltype.Float], lltype.Float)
        fptr = llhelper(lltype.Ptr(FUNC), float_return)
        calldescr = cpu.calldescrof(FUNC, FUNC.ARGS, FUNC.RESULT,
                                    EffectInfo.MOST_GENERAL)
        loop = self.parse("""
        [f0]
        i = force_token()
        f1 = call(ConstClass(fptr), i, f0, descr=calldescr)
        finish(f1, descr=finaldescr)
        """, namespace={'fptr': fptr, 'calldescr': calldescr,
                        'finaldescr': BasicFinalDescr(1)})
        token = JitCellToken()
        cpu.gc_ll_descr.init_nursery(20)
        cpu.setup_once()
        cpu.compile_loop(loop.inputargs, loop.operations, token)
        arg = longlong.getfloatstorage(2.3)
        frame = cpu.execute_token(token, arg)
        ofs = cpu.get_baseofs_of_frame_field()
        f = cpu.read_float_at_mem(frame, ofs)
        f = longlong.getrealfloat(f)
        assert f == 2.3 + 1.2

    def test_malloc_1(self):
        cpu = self.cpu
        sizeof = cpu.sizeof(self.S)
        sizeof.tid = 0
        size = sizeof.size
        loop = self.parse("""
        []
        p0 = call_malloc_nursery(%d)
        p1 = call_malloc_nursery(%d)
        p2 = call_malloc_nursery(%d) # this overflows
        guard_nonnull(p2, descr=faildescr) [p0, p1, p2]
        finish(p2, descr=finaldescr)
        """ % (size, size, size), namespace={'sizedescr': sizeof,
                        'finaldescr': BasicFinalDescr(),
                        'faildescr': BasicFailDescr()})
        token = JitCellToken()
        cpu.gc_ll_descr.collections = [[0, sizeof.size]]
        cpu.gc_ll_descr.init_nursery(2 * sizeof.size)
        cpu.setup_once()
        cpu.compile_loop(loop.inputargs, loop.operations, token)
        frame = cpu.execute_token(token)
        # now we should be able to track everything from the frame
        frame = lltype.cast_opaque_ptr(JITFRAMEPTR, frame)
        thing = frame.jf_frame[unpack_gcmap(frame)[0]]
        assert thing == rffi.cast(lltype.Signed, cpu.gc_ll_descr.nursery)
        assert cpu.gc_ll_descr.nursery_ptrs[0] == thing + sizeof.size
        assert rffi.cast(JITFRAMEPTR, cpu.gc_ll_descr.write_barrier_on_frame_called) == frame

    def test_call_release_gil(self):
        # note that we can't test floats here because when untranslated
        # people actually wreck xmm registers
        cpu = self.cpu
        l = []

        def before():
            l.append("before")

        def after():
            l.append("after")

        invoke_around_extcall(before, after)

        def f(frame, x):
            # all the gc pointers are alive p1 -> p7 (but not p0)
            assert bin(frame.jf_gcmap[0]).count('1') == 7
            assert x == 1
            return 2
        
        FUNC = lltype.FuncType([JITFRAMEPTR, lltype.Signed], lltype.Signed)
        fptr = llhelper(lltype.Ptr(FUNC), f)
        calldescr = cpu.calldescrof(FUNC, FUNC.ARGS, FUNC.RESULT,
                                    EffectInfo.MOST_GENERAL)        
        loop = self.parse("""
        [i0, p1, p2, p3, p4, p5, p6, p7]
        p0 = force_token()
        i1 = call_release_gil(ConstClass(fptr), p0, i0, descr=calldescr)
        guard_not_forced(descr=faildescr) [p1, p2, p3, p4, p5, p6, p7]
        finish(i1, descr=finaldescr)
        """, namespace={'fptr': fptr, 'calldescr':calldescr,
                        'faildescr': BasicFailDescr(),
                        'finaldescr': BasicFinalDescr()})
        token = JitCellToken()
        cpu.gc_ll_descr.init_nursery(100)
        cpu.setup_once()
        cpu.compile_loop(loop.inputargs, loop.operations, token)
        args = [lltype.nullptr(llmemory.GCREF.TO) for i in range(7)]
        frame = cpu.execute_token(token, 1, *args)
        frame = rffi.cast(JITFRAMEPTR, frame)
        assert frame.jf_frame[0] == 2
        assert l == ['before', 'after']

    def test_call_may_force_gcmap(self):
        cpu = self.cpu
        
        def f(frame, arg, x):
            assert not arg
            assert frame.jf_gcmap[0] & 31 == 0
            assert bin(frame.jf_gcmap[0]).count('1') == 3 # p1, p2, p3, but
            # not in registers
            frame.jf_descr = frame.jf_force_descr # make guard_not_forced fail
            assert x == 1
            return lltype.nullptr(llmemory.GCREF.TO)

        FUNC = lltype.FuncType([JITFRAMEPTR, llmemory.GCREF, lltype.Signed],
                               llmemory.GCREF)
        fptr = llhelper(lltype.Ptr(FUNC), f)
        calldescr = cpu.calldescrof(FUNC, FUNC.ARGS, FUNC.RESULT,
                                    EffectInfo.MOST_GENERAL)

        A = lltype.GcArray(lltype.Ptr(lltype.GcArray(lltype.Signed)))
        a = lltype.malloc(A, 3, zero=True)

        loop = self.parse("""
        [i0, p0]
        pf = force_token()
        p1 = getarrayitem_gc(p0, 0, descr=arraydescr)
        p2 = getarrayitem_gc(p0, 1, descr=arraydescr)
        p3 = getarrayitem_gc(p0, 2, descr=arraydescr)
        pdying = getarrayitem_gc(p0, 0, descr=arraydescr)
        px = call_may_force(ConstClass(fptr), pf, pdying, i0, descr=calldescr)
        guard_not_forced(descr=faildescr) [p1, p2, p3, px]
        finish(px, descr=finishdescr)
        """, namespace={'fptr': fptr, 'calldescr': calldescr,
                        'arraydescr': cpu.arraydescrof(A),
                        'faildescr': BasicFailDescr(1),
                        'finaldescr': BasicFinalDescr(2)})

        token = JitCellToken()
        cpu.gc_ll_descr.init_nursery(100)
        cpu.setup_once()
        cpu.compile_loop(loop.inputargs, loop.operations, token)
        frame = lltype.cast_opaque_ptr(JITFRAMEPTR,
                                       cpu.execute_token(token, 1, a))
        assert bin(frame.jf_gcmap[0]).count('1') == 4

    def test_call_gcmap_no_guard(self):
        cpu = self.cpu
        
        def f(frame, arg, x):
            assert not arg
            assert frame.jf_gcmap[0] & 31 == 0
            assert bin(frame.jf_gcmap[0]).count('1') == 3 # p1, p2, p3
            frame.jf_descr = frame.jf_force_descr # make guard_not_forced fail
            assert x == 1
            return lltype.nullptr(llmemory.GCREF.TO)

        FUNC = lltype.FuncType([JITFRAMEPTR, llmemory.GCREF, lltype.Signed],
                               llmemory.GCREF)
        fptr = llhelper(lltype.Ptr(FUNC), f)
        calldescr = cpu.calldescrof(FUNC, FUNC.ARGS, FUNC.RESULT,
                                    EffectInfo.MOST_GENERAL)

        A = lltype.GcArray(lltype.Ptr(lltype.GcArray(lltype.Signed)))
        a = lltype.malloc(A, 3, zero=True)

        loop = self.parse("""
        [i0, p0]
        pf = force_token()
        p1 = getarrayitem_gc(p0, 0, descr=arraydescr)
        p2 = getarrayitem_gc(p0, 1, descr=arraydescr)
        p3 = getarrayitem_gc(p0, 2, descr=arraydescr)
        pdying = getarrayitem_gc(p0, 0, descr=arraydescr)
        px = call(ConstClass(fptr), pf, pdying, i0, descr=calldescr)
        guard_false(i0, descr=faildescr) [p1, p2, p3, px]
        finish(px, descr=finishdescr)
        """, namespace={'fptr': fptr, 'calldescr': calldescr,
                        'arraydescr': cpu.arraydescrof(A),
                        'faildescr': BasicFailDescr(1),
                        'finaldescr': BasicFinalDescr(2)})

        token = JitCellToken()
        cpu.gc_ll_descr.init_nursery(100)
        cpu.setup_once()
        cpu.compile_loop(loop.inputargs, loop.operations, token)
        frame = lltype.cast_opaque_ptr(JITFRAMEPTR,
                                       cpu.execute_token(token, 1, a))
        assert bin(frame.jf_gcmap[0]).count('1') == 4
