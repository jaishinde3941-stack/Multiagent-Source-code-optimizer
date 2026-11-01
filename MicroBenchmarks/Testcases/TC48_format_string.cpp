// Category: Security Vulnerabilities
// Error: Format string vulnerability

#include <cstdio>

int main() {
    char userInput[100];
    
    printf("Enter a message: ");
    scanf("%99s", userInput);
    
    printf(userInput);  // ERROR: Format string vulnerability
    printf("\n");
    
    return 0;
}
