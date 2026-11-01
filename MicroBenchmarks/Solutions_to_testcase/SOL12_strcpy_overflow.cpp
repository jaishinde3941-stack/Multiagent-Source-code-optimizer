// Category: Array/Buffer Errors (Success Case)
// Expected Result: Use safe string functions or ensure buffer size is sufficient

#include <iostream>
#include <cstring>

int main() {
    char buffer[100];  // SUCCESS: Increased buffer size
    const char* longString = "This is a very long string that exceeds buffer size";
    
    strncpy(buffer, longString, sizeof(buffer) - 1);  // SUCCESS: Used strncpy
    buffer[sizeof(buffer) - 1] = '\0';
    
    std::cout << buffer << std::endl;
    
    return 0;
}
