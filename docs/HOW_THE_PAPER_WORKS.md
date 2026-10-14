# How the paper look works

Working notes on making a creature read as a paper piñata. They come from looking closely at how paper
piñata animals are drawn and built in games and by hand, from published accounts by artists, and from a lot of
trial and error. They are our own notes and still changing.

## Shape first

- A creature should be nameable from its black silhouette. If it is not, no pattern will save it.
- Strong, simple forms: a body, a head, a few limbs or fins, and one feature that says what it is.
- Roundness belongs to the model. The paper adds texture on top; it should not be asked to hide a lumpy form.

## Colour

- Flat, painterly colour. No gradients.
- Two or three neighbouring colours cover most of the body. One or two contrasting accents take the rest.
- Regions meet along curved borders, often drawn as a line with a row of short stitches beside it.

## Pattern

- Bold and few: a handful of large marks placed on purpose, never a busy all-over print.
- A small folk-art vocabulary goes a long way: stitch rows, dotted lines, a ring with short rays, target
  circles, zigzag bands, rows of triangles, wavy stripes, bars on limbs.

## The paper itself

Three things together make a surface read as paper:

1. **Scraps in the colour.** Short strips in staggered rows, each a slightly different tone, with a darker
   line under each where it shades the one below.
2. **The same pattern as relief.** The strips also drive the bump, so light catches their edges.
3. **Paper that stands off the body.** Either real overlapping strips (what the fish use), or thin shells
   just above the surface that show only where a scrap is, plus tabs of paper standing along edges so the
   outline goes ragged (what `tools/pinata_skin.py` does).

Things that went wrong along the way:

- Every strip the same height made them flicker against each other in renders. Staggering their heights fixed it.
- Fins rooted the wrong way round looked like they were blowing forward. Each streamer now sweeps back from
  its root.
- Too much loose paper buries faces and painted marks. Faces want shorter, sparser scraps than bodies.
- Painted detail smaller than a scrap disappears. Marks need to be several scraps wide.

## Faces and extras

- Eyes are simple: a white disc, a large dark pupil, sometimes a thin coloured rim. Expression comes from
  size, placement and what is painted round them, not from detail inside them.
- Ears, fins and tails read best as paper cards and streamers, not solid lumps.
- Decide the animal's character in one sentence before designing its face.

## Variants

One shape can carry many colourings, which makes variants cheap:

- **Colour variant:** the same fish in another palette.
- **Rare:** a special treatment (golden, midnight, albino, rainbow).
- **Wildcard:** the common fish with odd traits added (twin tail, giant eyes, fluffy, crown, long fins, chubby).
