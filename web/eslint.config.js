// PR 1.5 (16 nov): reglas de React (hooks), TypeScript y accesibilidad. Solo errores reales; el formato lo pone prettier.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import globals from "globals";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "test-results", "playwright-report"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "jsx-a11y": jsxA11y },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "off",
      // En un diálogo modal, llevar el foco al primer campo es lo que recomienda WAI-ARIA (patrón «Dialog»).
      "jsx-a11y/no-autofocus": "off",
      // Reglas pensadas para el React Compiler: avisan, no bloquean (el panel no lo usa).
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
    },
  },
);
