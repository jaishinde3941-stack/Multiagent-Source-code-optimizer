// Category: Array/Buffer Errors
// Error: sprintf buffer overflow

#include <iostream>
#include <cstdio>

int main() {
    char buffer[10];
    int value = 123456789;
    
    sprintf(buffer, "Value: %d - Extra text here", value);  // ERROR: Overflow
    std::cout << buffer << std::endl;
    
    return 0;
}
