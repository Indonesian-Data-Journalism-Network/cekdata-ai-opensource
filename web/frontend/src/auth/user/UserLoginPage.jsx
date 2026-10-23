import AuthForm from "../shared/AuthForm";
import { DEMO_LOGIN_ENABLED } from "../../config/api";

export default function UserLoginPage(props) {
  return (
    <AuthForm
      {...props}
      allowSignup
      allowForgotPassword
      title="User Sign In"
      subtitle="Masuk sebagai user untuk memakai fitur chat Cek Data AI."
      signupSubtitle="Daftar dengan Nama, Media/Organisasi, Email, dan Nomor handphone. Akun aktif setelah konfirmasi email/WhatsApp dan mendapat trial 3 chat."
      demoCredentials={DEMO_LOGIN_ENABLED ? { email: "demo@cekdata.ai", password: "cekdata2026" } : null}
    />
  );
}
