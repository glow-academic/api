<#-- Custom head.ftl for Glow theme -->
<#-- Override favicon to use Glow branding instead of Keycloak default -->
<#-- This file is included by Keycloak's base template.ftl -->

<#-- Geist font from Google Fonts (matching Next.js app) -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet" />

<#-- Favicon (SVG for modern browsers) -->
<link rel="icon" href="${url.resourcesPath}/favicon.svg" type="image/svg+xml" />

<#-- Favicon fallbacks (PNG and ICO for older browsers) -->
<link rel="icon" href="${url.resourcesPath}/img/favicon.png" type="image/png" />
<link rel="shortcut icon" href="${url.resourcesPath}/img/favicon.ico" />
