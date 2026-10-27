// Edit this file before the presentation. Anything left empty is shown honestly as "not set".
window.DEMO_CONFIG = {
  presenter: "",                                   // your name (optional)
  github: "https://github.com/Vilsee/clineval-ci",
  jenkins: "http://localhost:8080/job/clineval-ci/",
  vercel: "",                                      // your Vercel URL once deployed, e.g. https://clineval-ci.vercel.app
  timerMinutes: 10,
  // status: "done" | "partial" | "pending"  (shown as the chips on the rubric strip)
  rubric: {
    certification: { status: "pending", label: "Add certificate", course: "", issuer: "", completion: 0, url: "" },
    terraform:     { status: "partial", label: "Validated, not applied" },
    cicd:          { status: "done",    label: "Pipeline green" },
    azure:         { status: "pending", label: "Subscription pending", url: "" },   // set url to the VM address once deployed
    docs:          { status: "done",    label: "README + report" }
  }
};
