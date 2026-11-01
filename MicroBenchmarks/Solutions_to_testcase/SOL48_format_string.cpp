// Category: Security Vulnerabilities (Success Case)
// Expected Result: Use fixed format strings

#include <cstdio>

int main() {
    char userInput[100];
    
    printf("Enter a message: ");
    if (scanf("%99s", userInput) == 1) {
        printf("%s\n", userInput);  // SUCCESS: Fixed format string "%s"
    }
    
    return 0;
}
