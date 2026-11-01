// Category: Array/Buffer Errors (Success Case)
// Expected Result: Use snprintf to prevent buffer overflow

#include <iostream>
#include <cstdio>

int main() {
    char buffer[100];  // SUCCESS: Increased buffer size and used snprintf
    int value = 123456789;
    
    snprintf(buffer, sizeof(buffer), "Value: %d - Extra text here", value);
    std::cout << buffer << std::endl;
    
    return 0;
}
