# Checksum-verifying the gitleaks binary (S-10)

1. Download the release tarball manually and inspect it:
   curl -sSfL -o gitleaks.tar.gz \
     https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
2. Record its digest:  sha256sum gitleaks.tar.gz > tools/gitleaks.sha256
3. Commit tools/gitleaks.sha256. CI then verifies every download against it
   (see the Secrets step in .github/workflows/ci.yml).

Until the digest file exists, the Secrets gate runs as a warning, not a pass.
