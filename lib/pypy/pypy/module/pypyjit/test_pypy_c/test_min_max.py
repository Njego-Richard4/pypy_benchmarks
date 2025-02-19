import py
from pypy.module.pypyjit.test_pypy_c.test_00_model import BaseTestPyPyC

class TestMinMax(BaseTestPyPyC):

    def test_min_max(self):
        def main():
            i=0
            sa=0
            while i < 300:
                sa+=min(max(i, 3000), 4000)
                i+=1
            return sa
        log = self.run(main, [])
        assert log.result == 300*3000
        loop, = log.loops_by_filename(self.filepath)
        assert loop.match("""
            i7 = int_lt(i4, 300)
            guard_true(i7, descr=...)
            guard_not_invalidated(descr=...)
            i9 = int_add_ovf(i5, 3000)
            guard_no_overflow(descr=...)
            i11 = int_add(i4, 1)
            --TICK--
            jump(..., descr=...)
        """)
        

    def test_silly_max(self):
        def main():
            i = 13
            sa = 0
            while i < 30000:
                lst = range(i % 1000 + 2)
                sa += max(*lst) # ID: max
                i += 1
            return sa
        log = self.run(main, [])
        assert log.result == main()
        loop, = log.loops_by_filename(self.filepath)
        assert loop.match("""
            ...
            p76 = call_assembler(_, _, _, _, descr=...)
            ...
        """)
        loop2 = log.loops[0]
        loop2.match('''
        ...
        label(..., descr=...)
        ...
        label(..., descr=...)
        i17 = int_ge(i11, i7)
        guard_false(i17, descr=...)
        p18 = getarrayitem_gc(p5, i11, descr=...)
        i19 = int_add(i11, 1)
        setfield_gc(p2, i19, descr=...)
        guard_class(p18, ConstClass(W_IntObject), descr=...)
        i20 = getfield_gc_pure(p18, descr=...)
        i21 = int_gt(i20, i14)
        guard_true(i21, descr=...)
        jump(..., descr=...)
        ''')

    def test_iter_max(self):
        def main():
            i = 2
            sa = 0
            while i < 300:
                lst = range(i)
                sa += max(lst) # ID: max
                i += 1
            return sa
        log = self.run(main, [])
        assert log.result == main()
        loop, = log.loops_by_filename(self.filepath)
        # We dont want too many guards, but a residual call to min_max_loop
        guards = [n for n in log.opnames(loop.ops_by_id("max")) if n.startswith('guard')]
        assert len(guards) < 20
        assert loop.match("""
            ...
            p76 = call_assembler(_, _, _, _, descr=...)
            ...
        """)
