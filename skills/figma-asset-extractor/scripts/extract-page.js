// extract-page.js — (MCP fallback only) scans one Figma page read-only and returns JSON in the same shape as REST /v1/files.
// Do not use it when FIGMA_TOKEN is available — figma_bundle.py fetch does the same job without consuming context.
//
// Run: Read this file, change only the ARGS line, then send it as-is as the `use_figma` code (one page per call).
//      Save the return value as-is to <bundle>/raw/mcp-<pageId>-<offset>.json — figma_bundle.py build merges them.
//      If part.next is not null, change offset to that value and call again.
// No writes: it never creates or modifies nodes — the original file belongs to the designer.
// Return size: one screen tree can grow to tens of KB. If the output is truncated, reduce limit (default 6 screens).
const ARGS = { pageId: '__PAGE_ID__', offset: 0, limit: 6 };

const page = await figma.getNodeByIdAsync(ARGS.pageId);
if (!page || page.type !== 'PAGE') throw new Error('pageId is not a page: ' + ARGS.pageId);
await figma.setCurrentPageAsync(page);

const WEIGHT = { thin: 100, extralight: 200, light: 300, regular: 400, medium: 500, semibold: 600, bold: 700, extrabold: 800, black: 900 };
const weightOf = style => WEIGHT[style.toLowerCase().replace(/[\s-]|italic/g, '')] || 400;
const r2 = v => Math.round(v * 100) / 100;
const components = {}, componentSets = {};

function paint(p) {
  const o = { type: p.type, visible: p.visible === false ? false : undefined, opacity: p.opacity != null && p.opacity < 1 ? r2(p.opacity) : undefined };
  if (p.type === 'SOLID') o.color = { r: r2(p.color.r), g: r2(p.color.g), b: r2(p.color.b), a: 1 };
  else if (p.type === 'IMAGE') { o.imageRef = p.imageHash; o.scaleMode = p.scaleMode; }
  else if (p.type.startsWith('GRADIENT')) o.gradientStops = p.gradientStops.map(s => ({ position: r2(s.position), color: { r: r2(s.color.r), g: r2(s.color.g), b: r2(s.color.b), a: r2(s.color.a) } }));
  return o;
}

async function node(n, inInstance) {
  if (!n.visible) return null;
  const o = { id: n.id, type: n.type, name: n.name, absoluteBoundingBox: { x: Math.round(n.absoluteTransform[0][2]), y: Math.round(n.absoluteTransform[1][2]), width: Math.round(n.width), height: Math.round(n.height) } };
  if ('fills' in n && n.fills !== figma.mixed && n.fills.length) o.fills = n.fills.map(paint);
  if ('strokes' in n && n.strokes.length) { o.strokes = n.strokes.map(paint); o.strokeWeight = n.strokeWeight === figma.mixed ? 1 : n.strokeWeight; }
  if ('cornerRadius' in n) {
    if (n.cornerRadius === figma.mixed) o.rectangleCornerRadii = [n.topLeftRadius, n.topRightRadius, n.bottomRightRadius, n.bottomLeftRadius];
    else if (n.cornerRadius) o.cornerRadius = n.cornerRadius;
  }
  if ('effects' in n && n.effects.length) o.effects = n.effects.map(e => ({ type: e.type, visible: e.visible, radius: e.radius, spread: e.spread, offset: e.offset, color: e.color && { r: r2(e.color.r), g: r2(e.color.g), b: r2(e.color.b), a: r2(e.color.a) } }));
  if ('opacity' in n && n.opacity < 1) o.opacity = r2(n.opacity);
  if ('layoutMode' in n && n.layoutMode !== 'NONE') Object.assign(o, { layoutMode: n.layoutMode, itemSpacing: n.itemSpacing, paddingTop: n.paddingTop, paddingRight: n.paddingRight, paddingBottom: n.paddingBottom, paddingLeft: n.paddingLeft, primaryAxisAlignItems: n.primaryAxisAlignItems, counterAxisAlignItems: n.counterAxisAlignItems });
  if ('layoutPositioning' in n && n.layoutPositioning === 'ABSOLUTE') o.layoutPositioning = 'ABSOLUTE';
  if ('reactions' in n && n.reactions && n.reactions.length) o.interactions = n.reactions.map(r => ({ trigger: r.trigger && { type: r.trigger.type }, actions: (r.actions || [r.action]).filter(Boolean).map(a => ({ destinationId: a.destinationId })) }));
  if (n.type === 'TEXT') {
    o.characters = n.characters;
    const f = n.fontName === figma.mixed ? n.getRangeFontName(0, 1) : n.fontName;
    const size = n.fontSize === figma.mixed ? n.getRangeFontSize(0, 1) : n.fontSize;
    const lh = n.lineHeight === figma.mixed ? n.getRangeLineHeight(0, 1) : n.lineHeight;
    const ls = n.letterSpacing === figma.mixed ? n.getRangeLetterSpacing(0, 1) : n.letterSpacing;
    if (n.fills === figma.mixed) o.fills = n.getRangeFills(0, 1).map(paint);
    o.style = { fontFamily: f.family, fontWeight: weightOf(f.style), fontSize: size,
      lineHeightPx: lh.unit === 'PIXELS' ? lh.value : lh.unit === 'PERCENT' ? r2(lh.value * size / 100) : undefined, lineHeightUnit: lh.unit === 'AUTO' ? 'INTRINSIC_%' : 'PIXELS',
      letterSpacing: ls.unit === 'PIXELS' ? ls.value : r2(ls.value * size / 100), textAlignHorizontal: n.textAlignHorizontal };
  }
  if (n.type === 'COMPONENT_SET' || n.type === 'COMPONENT') {
    const isVariant = n.type === 'COMPONENT' && n.parent && n.parent.type === 'COMPONENT_SET';
    (n.type === 'COMPONENT_SET' ? componentSets : components)[n.id] = { key: n.key, name: n.name, description: n.description || '', componentSetId: isVariant ? n.parent.id : undefined };
    if (!isVariant) { try { o.componentPropertyDefinitions = n.componentPropertyDefinitions; } catch (e) { /* a component whose definition cannot be read is left without properties */ } }
  }
  if (n.type === 'INSTANCE') {
    const m = await n.getMainComponentAsync();
    if (m) {
      o.componentId = m.id;
      const set = m.parent && m.parent.type === 'COMPONENT_SET' ? m.parent : null;
      components[m.id] = { key: m.key, name: m.name, remote: m.remote, componentSetId: set ? set.id : undefined };
      if (set) componentSets[set.id] = { key: set.key, name: set.name, remote: set.remote };
    }
    if (n.componentProperties) o.componentProperties = Object.fromEntries(Object.entries(n.componentProperties).map(([k, v]) => [k, { value: v.value }]));
    // Inside an instance keep only the text — the structure belongs to the component definition (extract the component page along with it)
    o.children = n.findAllWithCriteria({ types: ['TEXT'] }).filter(t => t.visible).slice(0, 12).map(t => ({ id: t.id, type: 'TEXT', name: t.name, characters: t.characters, absoluteBoundingBox: { x: 0, y: 0, width: Math.round(t.width), height: Math.round(t.height) } }));
    return o;
  }
  if ('children' in n && n.children.length) {
    o.children = [];
    for (const c of n.children) { const k = await node(c, inInstance); if (k) o.children.push(k); }
  }
  return o;
}

const frames = [];
for (const n of page.children) {
  if (n.type === 'SECTION') { for (const c of n.children) if (c.type === 'FRAME') frames.push(c); }
  else if (n.type === 'FRAME') frames.push(n);
}
const children = [];
if (ARGS.offset === 0) for (const c of page.findAllWithCriteria({ types: ['COMPONENT_SET', 'COMPONENT'] })) {
  if (c.type === 'COMPONENT' && c.parent && c.parent.type === 'COMPONENT_SET') continue;
  const k = await node(c, false); if (k) children.push(k);
}
for (const f of frames.slice(ARGS.offset, ARGS.offset + ARGS.limit)) { const k = await node(f, false); if (k) children.push(k); }

return {
  name: figma.root.name,
  document: { children: [{ id: page.id, type: 'CANVAS', name: page.name, children }] },
  components, componentSets,
  _source: { fileKey: figma.fileKey, via: 'mcp' },
  part: { offset: ARGS.offset, limit: ARGS.limit, totalScreens: frames.length, next: ARGS.offset + ARGS.limit < frames.length ? ARGS.offset + ARGS.limit : null },
};
