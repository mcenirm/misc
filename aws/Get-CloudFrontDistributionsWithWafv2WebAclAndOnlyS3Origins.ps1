<#
.SYNOPSIS
    Retrieves CloudFront distributions that use WAFv2 web ACLs and have only S3 origins.

.DESCRIPTION
    This script lists all CloudFront distributions and filters them to find those that:
    - Use a WAFv2 web ACL (indicated by a non-null WebACLId).
    - Have only S3 origins (checked by verifying the origin's domain name).

.PARAMETER None
    This script does not take any parameters.

.EXAMPLE
    .\Get-CloudFrontDistributionsWithWafv2WebAclAndOnlyS3Origins.ps1
    This command runs the script to retrieve and display the filtered CloudFront distributions.

.NOTES
    Requires: AWS CLI v2 and appropriate IAM permissions to access CloudFront and WAFv2.
#>

# Get all CloudFront distributions
$distributions = aws cloudfront list-distributions | ConvertFrom-Json

# Initialize an array to hold the filtered distributions
$filteredDistributions = @()

# Loop through each distribution
foreach ($distribution in $distributions.DistributionList.Items) {
    # Check if the distribution has a WAFv2 web ACL
    if ($null -ne $distribution.WebACLId -and $distribution.WebACLId -ne "") {
        # Check if all origins are S3
        $allS3Origins = $true
        foreach ($origin in $distribution.Origins.Items) {
            if ($origin.DomainName -notlike "*.s3.amazonaws.com") {
                $allS3Origins = $false
                break
            }
        }

        # If it uses WAFv2 and has only S3 origins, add to the filtered list
        if ($allS3Origins) {
            $filteredDistributions += $distribution
        }
    }
}

# Output the filtered distributions
$filteredDistributions | Format-Table -Property Id, DomainName, WebACLId
