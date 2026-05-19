import ts from "typescript"

const projectRoot = process.cwd()
const configPath = ts.findConfigFile(projectRoot, ts.sys.fileExists, "tsconfig.app.json")

if (!configPath) {
  console.error("Unable to locate tsconfig.app.json for naming checks.")
  process.exit(1)
}

const configFile = ts.readConfigFile(configPath, ts.sys.readFile)
if (configFile.error) {
  console.error(ts.formatDiagnosticsWithColorAndContext([configFile.error], formatHost()))
  process.exit(1)
}

const parsedConfig = ts.parseJsonConfigFileContent(configFile.config, ts.sys, projectRoot)
const program = ts.createProgram({
  rootNames: parsedConfig.fileNames,
  options: parsedConfig.options,
})
const checker = program.getTypeChecker()

const deniedIdentifiers = new Set(["flag", "temp", "obj"])
const bareBooleanNames = new Map([
  ["active", "isActive"],
  ["disabled", "isDisabled"],
  ["loading", "isLoading"],
  ["saving", "isSaving"],
  ["locked", "isLocked"],
  ["required", "isRequired"],
])

const diagnostics = []

for (const sourceFile of program.getSourceFiles()) {
  if (sourceFile.isDeclarationFile) continue
  if (!sourceFile.fileName.startsWith(projectRoot)) continue
  if (!sourceFile.fileName.includes("\\src\\")) continue

  visit(sourceFile)
}

if (diagnostics.length > 0) {
  for (const diagnostic of diagnostics) {
    console.error(diagnostic)
  }
  process.exit(1)
}

function visit(node) {
  if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
    checkIdentifier(node.name, node)
  }

  ts.forEachChild(node, visit)
}

function checkIdentifier(identifierNode, variableNode) {
  const identifier = identifierNode.text
  if (deniedIdentifiers.has(identifier)) {
    diagnostics.push(formatIssue(identifierNode, `Avoid generic identifier "${identifier}". Use a domain-specific name instead.`))
    return
  }

  const suggestedBooleanName = bareBooleanNames.get(identifier)
  if (!suggestedBooleanName) {
    return
  }

  const variableType = checker.getTypeAtLocation(variableNode)
  if (isBooleanLike(variableType)) {
    diagnostics.push(
      formatIssue(
        identifierNode,
        `Boolean identifier "${identifier}" is too vague. Rename it to a prefixed form such as "${suggestedBooleanName}".`,
      ),
    )
  }
}

function isBooleanLike(type) {
  if (!type) return false
  const flags = type.getFlags()
  return Boolean(flags & (ts.TypeFlags.Boolean | ts.TypeFlags.BooleanLiteral))
}

function formatIssue(node, message) {
  const sourceFile = node.getSourceFile()
  const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart())
  return `${sourceFile.fileName}:${line + 1}:${character + 1} ${message}`
}

function formatHost() {
  return {
    getCanonicalFileName: (fileName) => fileName,
    getCurrentDirectory: () => projectRoot,
    getNewLine: () => ts.sys.newLine,
  }
}
