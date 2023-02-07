# NS1 CloudSync

## Publishing a new version

1. Bump the version and source code URL in `template.yaml` (`SemanticVersion`, `SourceCodeUrl`)
2. Build: `sam build`
3. Package: `sam package`
4. Commit to Github repo and make a new release
4. Publish: `sam publish`

Done.
