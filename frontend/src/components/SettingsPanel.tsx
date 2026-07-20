import { useState, type FormEvent } from "react";
import { changePassword, changeUsername, getLoginUser } from "../auth";

interface SettingsPanelProps {
  onCredentialsChanged?: () => void;
}

export function SettingsPanel({ onCredentialsChanged }: SettingsPanelProps) {
  const [username, setUsername] = useState(getLoginUser);
  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const [newUser, setNewUser] = useState(getLoginUser);
  const [userPass, setUserPass] = useState("");
  const [passMsg, setPassMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [userMsg, setUserMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const handlePassword = (e: FormEvent) => {
    e.preventDefault();
    setPassMsg(null);
    if (newPass !== confirmPass) {
      setPassMsg({ type: "err", text: "New password and confirmation do not match." });
      return;
    }
    const err = changePassword(currentPass, newPass);
    if (err) {
      setPassMsg({ type: "err", text: err });
      return;
    }
    setCurrentPass("");
    setNewPass("");
    setConfirmPass("");
    setPassMsg({ type: "ok", text: "Password updated. Use it next time you sign in." });
    onCredentialsChanged?.();
  };

  const handleUsername = (e: FormEvent) => {
    e.preventDefault();
    setUserMsg(null);
    const err = changeUsername(userPass, newUser);
    if (err) {
      setUserMsg({ type: "err", text: err });
      return;
    }
    setUsername(getLoginUser());
    setUserPass("");
    setUserMsg({ type: "ok", text: `Login username updated to “${getLoginUser()}”.` });
    onCredentialsChanged?.();
  };

  return (
    <div className="settings">
      <section className="settings-card">
        <div className="settings-card__head">
          <h2>Authentication</h2>
          <p>Update the admin login used for this portal (stored in this browser).</p>
        </div>

        <div className="settings-card__meta">
          <span className="settings-card__meta-label">Current login</span>
          <code>{username}</code>
        </div>

        <form className="settings-form" onSubmit={handlePassword}>
          <h3>Change password</h3>
          <label className="login-field">
            <span className="login-field__label">Current password</span>
            <input
              className="login-input"
              type="password"
              autoComplete="current-password"
              value={currentPass}
              onChange={(e) => setCurrentPass(e.target.value)}
              required
            />
          </label>
          <label className="login-field">
            <span className="login-field__label">New password</span>
            <input
              className="login-input"
              type="password"
              autoComplete="new-password"
              value={newPass}
              onChange={(e) => setNewPass(e.target.value)}
              required
              minLength={6}
            />
          </label>
          <label className="login-field">
            <span className="login-field__label">Confirm new password</span>
            <input
              className="login-input"
              type="password"
              autoComplete="new-password"
              value={confirmPass}
              onChange={(e) => setConfirmPass(e.target.value)}
              required
              minLength={6}
            />
          </label>
          {passMsg && (
            <div className={`alert ${passMsg.type === "ok" ? "alert--ok" : "alert--error"}`} role="status">
              {passMsg.text}
            </div>
          )}
          <button type="submit" className="btn btn--primary">
            Save password
          </button>
        </form>

        <form className="settings-form settings-form--spaced" onSubmit={handleUsername}>
          <h3>Change username</h3>
          <label className="login-field">
            <span className="login-field__label">Current password</span>
            <input
              className="login-input"
              type="password"
              autoComplete="current-password"
              value={userPass}
              onChange={(e) => setUserPass(e.target.value)}
              required
            />
          </label>
          <label className="login-field">
            <span className="login-field__label">New username</span>
            <input
              className="login-input"
              type="text"
              autoComplete="username"
              value={newUser}
              onChange={(e) => setNewUser(e.target.value)}
              required
              minLength={3}
            />
          </label>
          {userMsg && (
            <div className={`alert ${userMsg.type === "ok" ? "alert--ok" : "alert--error"}`} role="status">
              {userMsg.text}
            </div>
          )}
          <button type="submit" className="btn btn--soft">
            Save username
          </button>
        </form>
      </section>
    </div>
  );
}
