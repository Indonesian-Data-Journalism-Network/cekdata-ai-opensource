import AuthForm from "../shared/AuthForm";
import { DEMO_LOGIN_ENABLED } from "../../config/api";

export default function AdminLoginPage(props) {
  return (
    <AuthForm
      {...props}
      expectedRole="admin"
      title="Admin Sign In"
      subtitle="Masuk sebagai admin untuk mengelola user, batch data, preview, dan publish data."
      demoCredentials={DEMO_LOGIN_ENABLED ? { email: "admin@cekdata.ai", password: "cekdata2026" } : null}
    />
  );
}
