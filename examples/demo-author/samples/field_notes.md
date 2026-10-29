# Notes from a winter of sensor deployments

We spent the last four months running two small sensor networks outdoors. This post collects the
practical lessons; the papers have the numbers, and the [project page](https://example.org/breeze) has
the code.

## Batteries

Cold weather is hard on batteries, and harder than the data sheets suggest. At minus ten degrees our
cells delivered about two thirds of their rated capacity. We stress that this is not a fault of the
cells; it is chemistry. As a consequence, a schedule that lasts fifty days in autumn may last thirty in
January, and the dashboard should warn before a unit goes dark rather than after.

The cheapest fix was insulation. A sleeve of closed-cell foam around the battery pack kept it a few
degrees warmer during the night, which was enough to recover most of the lost capacity.[^foam]

## Mounting

Lamp posts are the obvious place for a sensor, and the city was happy to let us use them. Two things
went wrong. First, a sensor on the sunny side of a post heats up in the afternoon, and its readings
drift with it. Second, any bracket that needs tools makes swapping a unit slow. A good bracket allows to
swap a unit in a minute; ours took fifteen.

In what follows, a short checklist for the next deployment:

- Mount on the north side of the post, or under a small shade.
- Use a bracket that opens by hand.
- Label every unit with its id on two sides.
- Photograph the site when you install the unit, so you can tell later whether it was moved.

## Data

Keep the raw readings. Every cleaning step we applied early on, we later wanted to undo for one reason
or another. Put differently, storage is cheap and your judgment in week one is not.

Timestamps deserve the same care. Our units had no clock synchronization, and after a month the worst
of them was off by four minutes. The interval rule we used fits in one line:

```python
interval = min(max_interval, max(min_interval, eps / rate))
```

Correcting the drift after the fact turned out to be possible, but only because we had kept every
reading.

[^foam]: The foam came from a camping shop and cost less than the bracket.
