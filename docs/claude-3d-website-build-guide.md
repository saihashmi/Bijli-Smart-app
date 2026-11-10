# Claude + 3D Animated Website Build Guide

Claude turns prompts into working apps, documents, and automated workflows.

## Apps and tools people build

Claude works as a platform for coding, agents, and interactive artifacts.

- AI chatbots, customer support agents, and internal knowledge assistants
- Document analysis, research summaries, and data extraction from PDFs to JSON
- Code generators, debuggers, and full web apps built from plain language

## Creative and business workflows

People use Claude to replace repetitive writing, analysis, and planning work.

- Marketing copy, lesson plans, and long reports from uploaded files
- Spreadsheets, dashboards, and presentations created from notes or data
- "Second brain" systems, review agents, and learning libraries without coding

---

## Core Claude skills and plugins to install

Claude acts as the coder and director. These skills teach it how to build animated sites.

| Skill / plugin | What it does |
| --- | --- |
| **Site Kit / scroll-craft** | Builds "$10k-class" animated sites from one prompt. Install: `/plugin marketplace add iyography/ccc-plugins`, then `/plugin install site-kit@claudecodeclub` |
| **enhance-web-web3d** | Adds Three.js / React Three Fiber + GSAP scroll choreography to an existing site |
| **UI UX Pro Max** | Design judgment: typography, spacing, motion presets, so the result doesn't look "AI-generic" |
| **Three.js game skills + Blender MCP** | Real 3D scenes in the browser, plus modeling |
| **GSAP skills** | Scroll-triggered motion, timelines, and page transitions |

> Third-party plugins run code in your Claude Code session. Check the source repo before installing.

## Web libraries and workflow you'll need

Claude writes the code, but the site runs on these tools in the browser.

- **3D engine:** Three.js or React Three Fiber for scenes, cameras, lighting
- **Animation:** GSAP + ScrollTrigger for scroll scrub, pinning, exploded views; Framer Motion as an alternative engine
- **Asset pipeline:** generate video/image sequences with Kling.ai or Google Flow, convert to frames with ffmpeg, then sync the frames to scroll
- **Extras:** Lenis for smooth scroll, 21st.dev Magic MCP for React/Tailwind components, a fal.ai key if you want Claude to render videos/images

### Typical build flow

1. Collect 9–12 reference images
2. Claude + a skill generates the Three.js + GSAP code
3. Add assets
4. Deploy as static HTML

### Frame-sequence example (ffmpeg)

```bash
# Turn a generated clip into numbered WebP frames for scroll-scrubbing
ffmpeg -i hero.mp4 -vf "fps=30,scale=1600:-1" -c:v libwebp -quality 80 frames/frame_%04d.webp
```

No install is needed for basic demos: prompt "Build me [ANIMATION] with Three.js" (German: "Bau mir [ANIMATION] mit Three.js") and Claude outputs it directly.
