import * as store from "../store.js";
import * as state from "../state.js";
import { esc, breadcrumb, setTitle, toast } from "../ui.js";

export async function render(app) {
  setTitle("Sign in", "Sign in to keep your profile, saved jobs and alerts across devices.");
  if (!store.accountsAvailable()) {
    app.innerHTML = `<div class="page" style="max-width:640px">${breadcrumb([{ label: "Home", href: "#/" }, { label: "Sign in" }])}
      <h1>Accounts are not enabled yet</h1>
      <p>This site has not been connected to its account service. Everything still works: your profile, saved jobs and searches are kept on this device.</p>
      <a class="btn btn-primary" href="#/profile">Set up your profile</a></div>`;
    return;
  }
  if (store.user()) { location.hash = "#/dashboard"; return; }
  let modeSel = "signin";
  const draw = (msg = "", isError = false) => {
    app.innerHTML = `<div class="page" style="max-width:520px">
      ${breadcrumb([{ label: "Home", href: "#/" }, { label: modeSel === "signup" ? "Create account" : "Sign in" }])}
      <h1>${modeSel === "signup" ? "Create an account" : "Sign in"}</h1>
      <p class="muted">Keep your profile, saved jobs and alerts across devices. Anything you saved on this device is added to your account.</p>
      ${msg ? `<div class="callout ${isError ? "error" : ""}" role="${isError ? "alert" : "status"}">${esc(msg)}</div>` : ""}
      <form class="panel" id="authForm" novalidate>
        <div class="field"><label for="a-email">Email</label><input id="a-email" type="email" autocomplete="email" required></div>
        <div class="field"><label for="a-pass">Password</label><input id="a-pass" type="password" autocomplete="${modeSel === "signup" ? "new-password" : "current-password"}" minlength="8" required>
          ${modeSel === "signup" ? '<span class="hint">At least 8 characters.</span>' : ""}<span class="error" id="a-err"></span></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn btn-primary" type="submit" id="aSubmit">${modeSel === "signup" ? "Create account" : "Sign in"}</button>
          <button class="btn" type="button" id="aMagic">Email me a sign-in link</button></div>
      </form>
      <p style="margin-top:14px">${modeSel === "signup" ? 'Already have an account? <a href="#/signin" id="toggle">Sign in</a>' : 'New here? <a href="#/signin" id="toggle">Create an account</a>'}</p>
      <p class="small muted">By creating an account you agree to how we handle data, described in <a href="#/privacy">Privacy and your data</a>.</p></div>`;
    document.getElementById("toggle").addEventListener("click", (e) => { e.preventDefault(); modeSel = modeSel === "signup" ? "signin" : "signup"; draw(); });
    const form = document.getElementById("authForm");
    const email = document.getElementById("a-email");
    const pass = document.getElementById("a-pass");
    const err = document.getElementById("a-err");
    const validEmail = () => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.textContent = "";
      [email, pass].forEach((x) => x.removeAttribute("aria-invalid"));
      if (!validEmail()) { email.setAttribute("aria-invalid", "true"); err.textContent = "Enter a valid email address."; email.focus(); return; }
      if (pass.value.length < 8) { pass.setAttribute("aria-invalid", "true"); err.textContent = "The password must be at least 8 characters."; pass.focus(); return; }
      const btn = document.getElementById("aSubmit");
      btn.disabled = true; btn.setAttribute("aria-busy", "true");
      try {
        if (modeSel === "signup") {
          const r = await store.signUp(email.value.trim(), pass.value);
          if (r.needsConfirmation) { draw(`Check ${email.value.trim()} for a confirmation link, then sign in.`); return; }
        } else await store.signIn(email.value.trim(), pass.value);
        await state.load();
        toast("Signed in.");
        location.hash = "#/dashboard";
      } catch (e2) {
        err.textContent = /invalid login/i.test(e2.message) ? "The email or password is not correct." : e2.message;
        btn.disabled = false; btn.removeAttribute("aria-busy");
      }
    });
    document.getElementById("aMagic").addEventListener("click", async () => {
      if (!validEmail()) { email.setAttribute("aria-invalid", "true"); err.textContent = "Enter your email address first."; email.focus(); return; }
      try { await store.magicLink(email.value.trim()); draw(`A sign-in link was sent to ${email.value.trim()}. It expires in one hour.`); }
      catch (e2) { err.textContent = e2.message; }
    });
  };
  draw();
}
