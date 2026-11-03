import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";
import { AuthProvider } from "../auth/AuthProvider";
import { routerFuture } from "../routerFuture";

export function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={routerFuture}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}
