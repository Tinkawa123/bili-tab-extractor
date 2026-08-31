export const log = {
  info(msg: string): void {
    console.error(`  ${msg}`);
  },
  step(msg: string): void {
    console.error(`\x1b[36m▶\x1b[0m ${msg}`);
  },
  success(msg: string): void {
    console.error(`\x1b[32m✔\x1b[0m ${msg}`);
  },
  warn(msg: string): void {
    console.error(`\x1b[33m⚠\x1b[0m ${msg}`);
  },
  error(msg: string): void {
    console.error(`\x1b[31m✖\x1b[0m ${msg}`);
  },
  debug(msg: string): void {
    console.error(`\x1b[90m  ${msg}\x1b[0m`);
  },
};
