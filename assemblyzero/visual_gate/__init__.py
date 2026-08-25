"""The visual gate: render the contract early, serve the picture, halt for
the operator's eyes (#2518).

boostgauge #331 spent twelve spec review rounds across ten days arguing about
how to TEST a picture nobody had drawn. Rendered directly from the numeric
contract, the picture earned five concrete pieces of operator feedback in one
look. This package is that loop as a pipeline stage: render early, serve a
localhost page with Approve / Reject / Modify, fold the feedback into the
binding docs, and measure downstream expected values from the approved image.

First artifact type: static images, served locally, stdlib server only.
"""
