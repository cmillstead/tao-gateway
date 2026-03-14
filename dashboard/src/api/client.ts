import createClient from "openapi-fetch";
import type { paths } from "./schema";

const client = createClient<paths>({
  credentials: "include",
});

export default client;
