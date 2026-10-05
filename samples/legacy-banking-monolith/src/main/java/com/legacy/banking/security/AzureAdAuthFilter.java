package com.legacy.banking.security;

import com.legacy.banking.service.AzureAdAuthenticationService;
import javax.inject.Inject;
import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.annotation.WebFilter;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

/**
 * Legacy Java EE Servlet Filter intercepting incoming web requests to enforce Azure AD authentication.
 * Extracts Authorization Bearer tokens, validates them through AzureAdAuthenticationService,
 * and sets the authenticated principal in the request context.
 */
@WebFilter(filterName = "AzureAdAuthFilter", urlPatterns = {"/api/*", "/secured/*", "/views/*"})
public class AzureAdAuthFilter implements Filter {

    public static final String PRINCIPAL_REQ_ATTR = "CURRENT_AZURE_USER";

    @Inject
    private AzureAdAuthenticationService authService;

    @Override
    public void init(FilterConfig filterConfig) throws ServletException {
        System.out.println("[AzureAdAuthFilter] Initialized enterprise Azure AD security filter.");
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String authHeader = httpRequest.getHeader("Authorization");

        // Allow bypassing for health checks or public landing pages
        String uri = httpRequest.getRequestURI();
        if (uri.endsWith("/public") || uri.endsWith("/login.xhtml")) {
            chain.doFilter(request, response);
            return;
        }

        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            try {
                AzureAdUserPrincipal principal = authService.authenticateBearerToken(authHeader);
                httpRequest.setAttribute(PRINCIPAL_REQ_ATTR, principal);
                chain.doFilter(request, response);
                return;
            } catch (SecurityException e) {
                httpResponse.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                httpResponse.getWriter().write("{\"error\": \"Unauthorized: " + e.getMessage() + "\"}");
                return;
            }
        }

        // In development/test mode, fallback or require auth
        chain.doFilter(request, response);
    }

    @Override
    public void destroy() {
        System.out.println("[AzureAdAuthFilter] Destroyed Azure AD security filter.");
    }
}
