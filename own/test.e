#!/usr/bin/env rune

# Copyright 2004 Mark S. Miller, under the terms of the MIT X license
# found at http://www.opensource.org/licenses/mit-license.html ................

pragma.syntax("0.9")
pragma.enable("explicit-result-guard")

def EIteratable := <type:org.erights.e.elib.tables.EIteratable>

# /**
#  * Represents the body of a key-value iteration loop
#  */
# interface Each2Block(key, value, __continue) :void
def Each2Block := any

# /**
#  * Represents the body of a value-only iteration loop
#  */
# interface Each1Block(value, __continue) :void
def Each1Block := any

/**
 * Inspired by <a href=
 * "http://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node347.html">Series</a>.
 * <p>
 * We rely on an RColl's each2/1 method
 * <ul>
 * <li>not to retain the each2Block argument each2/1 exits (whether normally
 *     or otherwise), and
 * <li>to ignore the value returned by the each2Block.
 * </ul>
 * This module must only use the RCollStamp to approve RColls we can rely on to
 * implement this property, and must not let this stamp escape.
 */
interface RColl guards RCollStamp {
    to each2(each2Block :Each2Block) :void
}

interface Series extends RColl, EIteratable {
    # XXX Other method declarations with doc-comments should go here
}

def adapt1to2(each1Block :Each1Block) :Each2Block {
    return fn _,v,__continue { each1Block(v,__continue) }
}
/**
 *
 */
def makeSeries {

    /**
     * Makes a Series from an RColl or an EIteratable
     */
    to run(coll) :Series {
        switch (coll) {
            match rcoll :RColl {
                return makeSeries.fromRColl(rcoll)
            }
            match icoll :EIteratable {
                def rcoll implements RCollStamp {
                    to each2(var each2Block) :void {
                        try {
                            icoll.iterate(fn k,v {
                                escape __continue {
                                    each2Block(k,v,__continue)
                                }
                                null
                            })
                        } finally {
                            each2Block := Ref.broken("loop body disabled")
                        }
                    }
                }
                return makeSeries.fromRColl(rcoll)
            }
        }
    }

    /**
     * Make the infinite series of all the natural numbers in ascending order.
     * <p>
     * To avoid a non-termination, compose with an "until" transducer before
     * collecting.
     */
    to naturalNums() :Series {
        def alephNull implements RCollStamp {
            to each2(each2Block) :void {
                var i := 0
                __loop(fn {
                    escape __continue { each2Block(i, i, __continue) }
                    i += 1
                    true
                })
            }
        }
        return makeSeries.fromRColl(alephNull)
    }

    /**
     * Makes a series from an RColl we can rely on to implement the
     * RColl lifetime guarantees.
     * <p>
     * Expected to be for internal use only. (XXX Perhaps we should refactor
     * so this isn't exposed?)
     */
    to fromRColl(rcoll :RColl) :Series {

        /**
         * Paraphrasing the introduction of <a href=
         * "http://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node347.html"
         * >Series</a> which inspired ours:
         * <blockquote>
         * Series combine aspects of sequences, streams, and loops. Like
         * sequences, series represent totally ordered multi-sets of key-value
         * pairs. The series methods operate on whole series, rather than
         * extracting elements to be processed by other functions.
         * <p>
         * Like streams, series can represent unbounded sets of pairs and are
         * supported by on-demand evaluation: each element of a series is not
         * computed until it is needed.
         * </blockquote>
         * A series has two kinds of methods: collectors, which iterate the
         * series, and transducers which build new derived series from a given
         * base series. (Waters' remaining category, "scanners", is taken care
         * of by our makeSeries/1 function for building a series from a
         * non-series, and by makeSeries#naturalNums/0.)
         * <p>
         * Transducers accumulate their function arguments and those of their
         * base series into their derived series. The lifetime of one of these
         * function arguments includes the lifetimes of all series derived
         * from it.
         * <p>
         * Collectors iterate the series, potentially calling the original
         * EIteratable and any of the functions accumulated into the series.
         * The series should encapsulate all these, and ensure that they are
         * called only during a call to one of its collect methods.
         * <p>
         * The current E implementation of series does not do the kind of
         * optimization done by Waters. But it is written to enable the kind
         * of binding-time stage separation needed for partial evaluation
         * to unroll static compositions of transducers + a collector into an
         * efficient nested loop. This should produce much of the net effect.
         * Hopefully, we'll eventually find out.
         *
         * @see <a href=
         * "http://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node347.html"
         * >Series</a> by Richard Waters, appearing as Appendix A of
         * Common Lisp the Language by Guy Steele.
         */
        def series implements Series, RCollStamp, EIteratable {

            /**
             * Collects nothing from the series, but does iterate it, in order
             * to cause whatever side effects that causes.
             */
            to each2(each2Block) :void {
                rcoll.each2(each2Block)
            }

            /**
             * Collects nothing from the series, but does iterate it, in order
             * to cause whatever side effects that causes.
             */
            to each(each1Block) :void {
                rcoll.each2(adapt1to2(each1Block))
            }

            /**
             * Collects nothing from the series, but does iterate it, in order
             * to cause whatever side effects that causes.
             */
            to iterate(assocFn) :void {
                rcoll.each2(fn k,v,_ { assocFn(k,v) })
            }

            /**
             * Collects a list of the values of the series
             */
            to asList() :List {
                def result := [].diverge()
                rcoll.each2(fn _,v,_ {
                    result.push(v)
                })
                return result.snapshot()
            }

            /**
             * Collects a map of the key-value associations of the series.
             * <p>
             * If there are multiple associations for the same key, the last
             * one wins.
             */
            to asMap() :Map {
                def result := [].asMap().diverge()
                rcoll.each2(fn k,v,_ {
                    result[k] := v
                })
                return result.snapshot()
            }

            /**
             * Collects a left-fold by repeated application of a
             * 2block-function representing a binary function. Seed should
             * typically be the identity element for that function.
             * <p>
             * Iterations in which __continue is called are skipped.
             */
            to fold(seed, fold2Block) :any {
                var result := seed
                rcoll.each2(fn _,v,__continue {
                    result := fold2Block(result,v,__continue)
                })
                return result
            }

            to sum() :int {
                return series.fold(0, fn x,y,_ {x+y})
            }

            /**
             * Transduces into the subset for which test2Block(k,v,_) passes.
             */
            to filter2(test2Block) :Series {
                def filtered implements RCollStamp {
                    to each2(each2Block) :void {
                        rcoll.each2(fn k,v,__continue {
                            if (test2Block(k,v,__continue)) {
                                each2Block(k,v,__continue)
                            }
                        })
                    }
                }
                return makeSeries.fromRColl(filtered)
            }

            /**
             * Transduces into the subset for which test1Block(v,_) passes.
             * <p>
             * Like Smalltalk's #select:
             */
            to filter(test1Block) :Series {
                return series.filter2(adapt1to2(test1Block))
            }

            /**
             * Transduces into the subset until test2Block(k,v,_) passes.
             */
            to until2(test2Block) :Series {
                def untiller implements RCollStamp {
                    to each2(each2Block) :void {
                        rcoll.each2(fn k,v,__continue {
                            if (test2Block(k,v,__continue)) {
                                return
                            }
                            each2Block(k,v,__continue)
                        })
                    }
                }
                return makeSeries.fromRColl(untiller)
            }

            /**
             * Transduces into the subset until test1Block(v,_) passes.
             */
            to until(test1Block) :Series {
                return series.until2(adapt1to2(test1Block))
            }

            /**
             * Transduces into a series mapping from the same keys to
             * the values resulting from map2Block(k,v,_).
             */
            to map2(map2Block) :Series {
                def mapped implements RCollStamp {
                    to each2(each2Block) :void {
                        rcoll.each2(fn k,v,__continue {
                            def v2 := map2Block(k,v,__continue)
                            each2Block(k,v2,__continue)
                        })
                    }
                }
                return makeSeries.fromRColl(mapped)
            }

            /**
             * Transduces into a series mapping from the same keys to
             * the values resulting from map1Block(v,_).
             * <p>
             * Like Smalltalk's #collect:
             */
            to map(map1Block) :Series {
                return series.map2(adapt1to2(map1Block))
            }

            /**
             * Given an iter2Block that produces a collection, splice2
             * transduces into a series that's a one level flattening of each
             * of the series produced from the associations in its base series.
             */
            to splice2(iter2Block) :Series {
                def splicer implements RCollStamp {
                    to each2(each2Block) :void {
                        rcoll.each2(fn k,v,__continue {
                            def sub := makeSeries(iter2Block(k,v,__continue))
                            sub.each2(each2Block)
                        })
                    }
                }
                return makeSeries.fromRColl(splicer)
            }

            /**
             * Given a iter1Block function that produces an collection, splice
             * transduces into a series that's a one level flattening of each
             * of the series produced from the values in its base series.
             */
            to splice(iter1Block) :Series {
                return series.splice2(adapt1to2(iter1Block))
            }
        }
        return series
    }
}

