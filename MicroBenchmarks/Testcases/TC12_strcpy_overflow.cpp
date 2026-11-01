// Category: Array/Buffer Errors
// Error: Stack buffer overflow with strcpy

#include <iostream>
#include <cstring>

int main() {
    char buffer[10];
    const char* longString = "This is a very long string that exceeds buffer size";
    
    strcpy(buffer, longString);  // ERROR: Buffer overflow
    std::cout << buffer << std::endl;
    
    return 0;
}
