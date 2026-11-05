// extensions.js: Margin's own page module, in the local layer (ENLENS 0.13.6). ENLENS's releases never edit it.
//
// What Margin adds to ENLENS's page through registry.js: the names and links of its draft jobs in the sidebar, and
// the result page's link back to the draft a claim comes from. See docs/EXTENDING.md.
const draftLink = (j) => (j.scope ? `#/drafts/${encodeURIComponent(j.scope)}` : "#/drafts");

export default {
  jobKinds: {
    "draft-find": { icon: "file-pen", text: "Finding the claims in a draft", link: draftLink, withJob: true },
    "draft-check": { icon: "file-pen", text: "Checking a draft's claims", link: draftLink, withJob: true },
  },
  origins: {
    draft: { eyebrow: "Back to your draft", meta: "a claim of your draft", href: (id) => `#/drafts/${encodeURIComponent(id)}` },
  },
};
