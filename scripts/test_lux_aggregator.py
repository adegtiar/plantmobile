#!/usr/bin/env python3
from datetime import datetime

from plantmobile.common import LuxAggregator, LuxReading

l1 = LuxReading(1, 2, 3, 4, 5, datetime(1900, 1, 1))
l2 = LuxReading(3, 4, 5, 6, 7, datetime(2100, 1, 1))
agg = LuxAggregator()
assert not agg, "empty aggregator must have length 0"
agg.add(l1)
agg.add(l2)
assert len(agg) == 2
print(agg.average())
