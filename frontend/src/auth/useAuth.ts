import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "./context";

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth doit être utilisé dans un <AuthProvider>");
  }
  return value;
}
